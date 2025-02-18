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
video_width, video_height = None, None
click_coordinates = []  # Stored as pixel coordinates (origin bottom-left)
calibration_done = False
rvec, tvec, camera_matrix = None, None, None

# World coordinates for the four calibration points (Z=0 plane)
world_coordinates = np.array([
    [0, 0, 0],
    [1, 0, 0],
    [1, 1, 0],
    [0, 1, 0]
], dtype=np.float32)

def initialize_video(video_path):
    global video_capture, width, height, video_width, video_height
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
    glEnable(GL_DEPTH_TEST)
    texture_id = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, texture_id)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

def draw_grid():
    # Draw grid lines on the Z=0 plane with 1-unit spacing
    glDisable(GL_TEXTURE_2D)
    glColor3f(0.5, 0.5, 0.5)
    glBegin(GL_LINES)
    for i in range(-5, 6):
        glVertex3f(i, -5, 0)
        glVertex3f(i,  5, 0)
        glVertex3f(-5, i, 0)
        glVertex3f( 5, i, 0)
    glEnd()
    glEnable(GL_TEXTURE_2D)

def draw_axes():
    # glDisable(GL_LIGHTING)
    glDisable(GL_TEXTURE_2D)
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
    glEnable(GL_TEXTURE_2D)
    # glEnable(GL_LIGHTING)

def draw_dots():
    glDisable(GL_TEXTURE_2D)
    glColor3f(0, 1, 0)
    glPointSize(5.0)
    glBegin(GL_POINTS)
    for x, y in click_coordinates:
        corrected_y = height - y
        # w_x, w_y = image2window(x, y)
        glVertex2f(x, corrected_y)
    glEnd()
    glEnable(GL_TEXTURE_2D)

def display():
    global video_capture, texture_id, click_coordinates, calibration_done, rvec, tvec, camera_matrix

    # --- 2D Rendering: Video background and click dots ---
    ret, frame = video_capture.read()
    if not ret:
        video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
        ret, frame = video_capture.read()
        if not ret:
            return

    # Flip the frame vertically to match our coordinate system.
    frame = cv2.flip(frame, 0)
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

    # Set up an orthographic projection for the video.
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, width, 0, height) # put ortho matrix on projection stack
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity() # put identity on modelview stack

    glDisable(GL_DEPTH_TEST)
    glBindTexture(GL_TEXTURE_2D, texture_id)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, frame.shape[1], frame.shape[0],
                 0, GL_RGB, GL_UNSIGNED_BYTE, frame)

    glColor3f(1, 1, 1)
    glBegin(GL_QUADS)
    glTexCoord2f(0, 0); glVertex2f(0, 0)
    glTexCoord2f(1, 0); glVertex2f(width, 0)
    glTexCoord2f(1, 1); glVertex2f(width, height)
    glTexCoord2f(0, 1); glVertex2f(0, height)
    glEnd()

    # Draw the click dots.
    draw_dots()

    glEnable(GL_DEPTH_TEST)
    glPopMatrix()  # Restore modelview
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()  # restore projection
    glMatrixMode(GL_MODELVIEW)

    # --- 3D Rendering: Grid and Axes projected via calibration ---
    if calibration_done:
        # Set up the projection matrix from the calibrated intrinsics.
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        near = 0.1
        far = 100.0
        # Use standard formulas:
        # left = -c_x * near / f_x, right = (width - c_x)* near / f_x,
        # bottom = -c_y * near / f_y, top = (height - c_y)* near / f_y
        c_x = camera_matrix[0, 2]
        c_y = camera_matrix[1, 2]
        f_x = camera_matrix[0, 0]
        f_y = camera_matrix[1, 1]
        left = -c_x * near / f_x
        right = (width - c_x) * near / f_x
        bottom = -c_y * near / f_y
        top = (height - c_y) * near / f_y
        glFrustum(left, right, bottom, top, near, far)

        # Build the modelview matrix from the calibration extrinsics.
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()

        # Obtain rotation matrix from rvec and build camera pose matrix.
        R, _ = cv2.Rodrigues(rvec)
        M = np.eye(4, dtype=np.float32)
        M[:3, :3] = R
        M[:3, 3] = tvec.flatten()

        M[1, :] *= -1
        M[2, :] *= -1
        view_matrix = M

        glLoadMatrixf(view_matrix.T)  # OpenGL expects column-major order

        # Draw grid (which lies on the Z=0 plane in world space) and axes at (0,0,0).
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

def window2image(x, y):
    # corrected_y = height - y
    video_x = (video_width / width) * x
    video_y = (video_height / height) * y
    return video_x, video_y

def image2window(x, y):
    window_x = (width / video_width) * x
    window_y = (height / video_height) * y
    corrected_y = height - window_y
    return window_x, corrected_y # window_y

def mouse_click(button, state, x, y):
    print(f"{x}, {y}")
    global click_coordinates, width, height, video_width, video_height
    if button == GLUT_LEFT_BUTTON and state == GLUT_DOWN:
        # Convert y from top-left to bottom-left
        if len(click_coordinates) >= 4:
            click_coordinates.pop(0)
        # video_x, video_y = window2image(x, y)
        click_coordinates.append((x, y))
        print(f"Click at: ({x}, {y})")

def compute_camera_parameters():
    global calibration_done, rvec, tvec, camera_matrix, click_coordinates, video_width
    if len(click_coordinates) != 4:
        print("Need exactly 4 click coordinates to compute camera parameters.")
        return

    # Use the stored pixel coordinates (origin at bottom-left)
    image_points = np.array(click_coordinates, dtype=np.float32)
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

