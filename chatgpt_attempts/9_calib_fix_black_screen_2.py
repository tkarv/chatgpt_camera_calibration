import cv2
import numpy as np
import argparse
from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *

# Global variables
video_capture = None
texture_id = None
width, height = 800, 600
click_coordinates = []
calibration_done = False
rvec, tvec, camera_matrix = None, None, None

# World coordinates for the four selected points (for calibration)
world_coordinates = np.array([
    [0, 0, 0],
    [1, 0, 0],
    [1, 1, 0],
    [0, 1, 0]
], dtype=np.float32)

def initialize_video(video_path):
    global video_capture, width, height
    video_capture = cv2.VideoCapture(video_path)
    if not video_capture.isOpened():
        print("Error: Could not open video file.")
        exit(1)
    
    video_width = int(video_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    video_height = int(video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    aspect_ratio = video_width / video_height
    
    height = min(600, video_height)
    width = int(height * aspect_ratio)

def initialize_gl():
    global texture_id
    glEnable(GL_TEXTURE_2D)
    glEnable(GL_DEPTH_TEST)  # For 3D rendering of grid and axes
    texture_id = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, texture_id)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

def draw_grid():
    glColor3f(0.5, 0.5, 0.5)
    glBegin(GL_LINES)
    for i in range(-5, 6):
        glVertex3f(i, -5, 0)
        glVertex3f(i, 5, 0)
        glVertex3f(-5, i, 0)
        glVertex3f(5, i, 0)
    glEnd()

def draw_axes():
    glBegin(GL_LINES)
    # X-axis in red
    glColor3f(1, 0, 0)
    glVertex3f(0, 0, 0)
    glVertex3f(1, 0, 0)
    # Y-axis in green
    glColor3f(0, 1, 0)
    glVertex3f(0, 0, 0)
    glVertex3f(0, 1, 0)
    # Z-axis in blue
    glColor3f(0, 0, 1)
    glVertex3f(0, 0, 0)
    glVertex3f(0, 0, 1)
    glEnd()

def display():
    global video_capture, texture_id, click_coordinates, calibration_done

    # --- Draw video background and dot overlays in 2D ---
    ret, frame = video_capture.read()
    if not ret:
        video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
        ret, frame = video_capture.read()
        if not ret:
            return

    frame = cv2.flip(frame, 0)
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Clear both color and depth buffers.
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

    # Switch to 2D orthographic projection for the video background.
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, width, 0, height)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    # Disable depth testing for the background quad.
    glDisable(GL_DEPTH_TEST)

    # Bind the video frame as a texture.
    glBindTexture(GL_TEXTURE_2D, texture_id)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, frame.shape[1], frame.shape[0],
                 0, GL_RGB, GL_UNSIGNED_BYTE, frame)

    # Draw a quad that fills the window.
    glColor3f(1, 1, 1)
    glBegin(GL_QUADS)
    glTexCoord2f(0, 0); glVertex2f(0, 0)
    glTexCoord2f(1, 0); glVertex2f(width, 0)
    glTexCoord2f(1, 1); glVertex2f(width, height)
    glTexCoord2f(0, 1); glVertex2f(0, height)
    glEnd()

    # Draw green dots for the stored click coordinates (convert normalized to pixel space)
    glColor3f(0, 1, 0)
    glPointSize(5.0)
    glBegin(GL_POINTS)
    for norm_x, norm_y in click_coordinates:
         pixel_x = (norm_x + 1) * width / 2
         pixel_y = (1 - norm_y) * height / 2
         glVertex2f(pixel_x, pixel_y)
    glEnd()

    # Restore previous matrices.
    glEnable(GL_DEPTH_TEST)
    glPopMatrix()  # Modelview
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

    # --- Draw grid and axes in 3D perspective (only if calibration is done) ---
    if calibration_done:
         glMatrixMode(GL_PROJECTION)
         glPushMatrix()
         glLoadIdentity()
         gluPerspective(45, width / height, 0.1, 100.0)
         glMatrixMode(GL_MODELVIEW)
         glPushMatrix()
         glLoadIdentity()
         # Position the camera so the grid and axes are visible.
         glTranslatef(0, 0, -5)
         draw_grid()
         draw_axes()
         glPopMatrix()
         glMatrixMode(GL_PROJECTION)
         glPopMatrix()
         glMatrixMode(GL_MODELVIEW)

    glutSwapBuffers()

def reshape(w, h):
    glViewport(0, 0, w, h)
    global width, height
    width, height = w, h

def idle():
    glutPostRedisplay()

def mouse_click(button, state, x, y):
    global click_coordinates, width, height
    if button == GLUT_LEFT_BUTTON and state == GLUT_DOWN:
        norm_x = (x / width) * 2 - 1
        norm_y = -((y / height) * 2 - 1)
        if len(click_coordinates) >= 4:
            click_coordinates.pop(0)
        click_coordinates.append((norm_x, norm_y))

def compute_camera_parameters():
    global calibration_done, rvec, tvec, camera_matrix, click_coordinates
    if len(click_coordinates) != 4:
        print("Need exactly 4 click coordinates to compute camera parameters.")
        return

    image_points = np.array([
        [(x + 1) * width / 2, (1 - y) * height / 2] for x, y in click_coordinates
    ], dtype=np.float32)

    focal_length = width  # Rough approximation
    camera_matrix = np.array([
        [focal_length, 0, width / 2],
        [0, focal_length, height / 2],
        [0, 0, 1]
    ], dtype=np.float32)

    dist_coeffs = np.zeros((4, 1), dtype=np.float32)
    success, rvec, tvec = cv2.solvePnP(world_coordinates, image_points, camera_matrix, dist_coeffs)

    if success:
        calibration_done = True
        print("Calibration successful!")
        print("Rotation Vector:", rvec.flatten())
        print("Translation Vector:", tvec.flatten())
    else:
        print("Failed to compute camera parameters.")

def key_pressed(key, x, y):
    if key == b'c':
        compute_camera_parameters()

def main():
    parser = argparse.ArgumentParser(description="OpenGL Video Player using OpenCV")
    parser.add_argument("video_path", help="Path to the video file")
    args = parser.parse_args()

    initialize_video(args.video_path)

    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(width, height)
    glutCreateWindow(b"OpenGL Video Player")

    initialize_gl()
    glutDisplayFunc(display)
    glutReshapeFunc(reshape)
    glutMouseFunc(mouse_click)
    glutKeyboardFunc(key_pressed)
    glutIdleFunc(idle)

    glutMainLoop()
    video_capture.release()

if __name__ == "__main__":
    main()

