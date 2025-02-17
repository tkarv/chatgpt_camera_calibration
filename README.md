# What is this?

Tried to get ChatGPT (as of 2025/02/17) to create a Python script to perform
camera calibration on a video given 4 points on a plane. It implemented the
video rendering (* frame rate is not taken into account), image coordinate
rendering (* color was not as specified), and camera calibration (* first try
used an OpenCV function that requires more points) all correctly-ish, but
struggled to render a grid on the defined plane. That's the point where I gave
up.

# Attempts

## `1_calib.py`

Shows the video. Aspect ratio is wrong. Didn't even ask for the calibration code at this
point.

## `2_calib_ar.py`

Fixed the aspect ratio of the video as asked (keeping maximum height to 600).

## `3_calib_dots.py`

Asked to add functionality where user could click on the video and it would
keep last 4 click coordinates in an array. Worked correctly but whole screen
now has a green tint. Also dots are rendered black instead of green as asked.

## `4_calib_dots_fix_tint.py`

Fixed the green tint as asked. Dots still rendered black.

## `5_calib_calc_calib.py`

Finally asked to calculate calibration based on the 4 user provided image
coordinates. Fails at doing that due to using OpenCV function that requires
more points than provided.

## `6_calib_fixed_calib.py`

Now uses the right function (`solvePnP`) to calculate camera calibration.

## `7_calib_render_grid_axes.py`

Asked to add a rendering function that would render a grid and coordinate axes
based on the camera calibration. Renders a black screen instead (no video).

## `8_calib_fix_black_screen.py`

Asked to fix the black screen. Still renders a black screen.

## `9_calib_fix_black_screen_2.py`

Now renders video correctly. No grid nor axes. Y-coordinate flip is not
performed correctly for clicked coordinates.

## `10_calib_fix_ycoord_grid.py`

Fixed Y-coordinate flip. Grid is rendered in camera coordinates(?) instead of
world coordinates.

## `11_calib_fix_grid_projection.py`

Grid is now projected, but there is an issue with the orientation of the grid.
It does not conform to the plane defined by the 4 points. Maybe an issue with
coordinate system difference between OpenCV and OpenGL?

## `12_calib_fix_coordinate_system.py`

Still exhibiting the same issue. Gave up.
