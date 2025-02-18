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

# World coordinates for the four selected points
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
    texture_id = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, texture_id)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

def display():
    global video_capture, texture_id, click_coordinates
    
    ret, frame = video_capture.read()
    if not ret:
        video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
        return
    
    frame = cv2.flip(frame, 0)
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    
    glBindTexture(GL_TEXTURE_2D, texture_id)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, frame.shape[1], frame.shape[0], 0, GL_RGB, GL_UNSIGNED_BYTE, frame)
    
    glColor3f(1, 1, 1)  # Ensure correct color balance for texture rendering
    glBegin(GL_QUADS)
    glTexCoord2f(0, 0); glVertex2f(-1, -1)
    glTexCoord2f(1, 0); glVertex2f(1, -1)
    glTexCoord2f(1, 1); glVertex2f(1, 1)
    glTexCoord2f(0, 1); glVertex2f(-1, 1)
    glEnd()
    
    # Render green dots at click coordinates
    glColor3f(0, 1, 0)
    glPointSize(5.0)
    glBegin(GL_POINTS)
    for x, y in click_coordinates:
        glVertex2f(x, y)
    glEnd()
    
    glutSwapBuffers()

def reshape(w, h):
    glViewport(0, 0, w, h)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluOrtho2D(-1, 1, -1, 1)
    glMatrixMode(GL_MODELVIEW)

def idle():
    glutPostRedisplay()

def mouse_click(button, state, x, y):
    global click_coordinates
    if button == GLUT_LEFT_BUTTON and state == GLUT_DOWN:
        norm_x = (x / width) * 2 - 1
        norm_y = -((y / height) * 2 - 1)
        if len(click_coordinates) >= 4:
            click_coordinates.pop(0)
        click_coordinates.append((norm_x, norm_y))

def compute_camera_parameters():
    if len(click_coordinates) != 4:
        print("Need exactly 4 click coordinates to compute camera parameters.")
        return
    
    # Convert normalized coordinates to pixel coordinates
    image_points = np.array([
        [(x + 1) * width / 2, (1 - y) * height / 2] for x, y in click_coordinates
    ], dtype=np.float32)
    
    # Assume a simple pinhole camera model with a focal length approximation
    focal_length = width  # Rough approximation
    camera_matrix = np.array([
        [focal_length, 0, width / 2],
        [0, focal_length, height / 2],
        [0, 0, 1]
    ], dtype=np.float32)
    
    # No lens distortion assumed
    dist_coeffs = np.zeros((4, 1), dtype=np.float32)
    
    # Solve for extrinsics using solvePnP
    success, rvec, tvec = cv2.solvePnP(world_coordinates, image_points, camera_matrix, dist_coeffs)
    
    if success:
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
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB)
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

