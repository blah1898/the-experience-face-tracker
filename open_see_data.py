""" open_see_data.py
Defines the OpenSeeData class with some helping types
Based on the Unity plugin provided by OpenSeeFace in Unity/OpenSee.cs.
"""
from dataclasses import dataclass
from functools import cache
from typing import List, Tuple, NamedTuple
import struct

NUMBER_OF_POINTS = 68

class Vector2(NamedTuple):
    x: float
    y: float

class Vector3(NamedTuple):
    x: float
    y: float
    z: float

class Quaternion(NamedTuple):
    w: float
    x: float
    y: float
    z: float

@dataclass(frozen=True)
class OpenSeeFeatures:
    eye_left: float
    """Indicates wether the left eye is opened (0) or closed (-1). A value of 1
    means open wider than normal."""

    eye_right: float
    """Indicates wether the right eye is opened (0) or closed (-1). A value of
    1 means open wider than normal."""

    eyebrow_steepness_left: float
    """Indicates how steep the left eyebrow is, compared to the median
    steepness."""

    eyebrow_up_down_left: float
    """Indicates how far up or down the left eyebrow is, compared to it's
    median position."""

    eyebrow_quirk_left: float
    """Indicates how quirked the left eyebrow is, compared to it's median
    position."""

    eyebrow_steepness_right: float
    """Indicates how steep the right eyebrow is, compared to the median
    steepness."""

    eyebrow_up_down_right: float
    """Indicates how far up or down the right eyebrow is, compared to it's
    median position."""

    eyebrow_quirk_right: float
    """Indicates how quirked the right eyebrow is, compared to it's median
    position."""

    mouth_corner_up_down_left: float
    """Indicates how far up or down the left mouth corner is, compared to it's
    median position."""

    mouth_corner_in_out_left: float
    """Indicates how far in or out the left mouth corner is, compared to it's
    median position."""

    mouth_corner_up_down_right: float
    """Indicates how far up or down the right mouth corner is, compared to it's
    median position."""

    mouth_corner_in_out_right: float
    """Indicates how far in or out the right mouth corner is, compared to it's
    median position."""

    mouth_open: float
    """Indicates how open or closed the mouth is, compared to it's median
    pose."""

    mouth_wide: float
    """Indicates how wide the mouth is, compared to it's median pose"""


@dataclass(frozen=True)
class OpenSeeData:
    time: float
    """The time this tracking data was captured at."""

    id: int
    """ID of the tracked face. When tracking multiple faces, they might get
    reordered due to faces coming and going, but as long as tracking is not
    lost on a face, its id should stay the same. Face ids depend only on the
    order of first detection and location of the faces. """

    camera_resolution: Vector2
    """The resolution of the cmaera of video being tracked."""

    right_eye_open: float
    """How likely it is that the right eye is open."""

    left_eye_open: float
    """How likely it is that the left eye is open."""

    # @property
    # def right_gaze(self) -> Quaternion:
    #     """Rotation of the right eyeball."""

    # @property
    # left_gaze: Quaternion
    #     """Rotation of the left eyeball."""

    got_3d_points: bool
    """If 3D points have been successfully estimated from the 2D points. If
    false, do not realy on pose or 3D data."""

    fit_3d_error: float
    """The error for fitting the original 3D points. It shouldn't matter much,
    but if it is very high, something is probably wrong."""

    @property
    def rotation(self) -> Vector3:
        """Rotation vector for the 3D points to turn into the estimated face
        pose. Rotation is pitch, yaw, roll."""
        x = -self.euler.x + 180 % 360
        z = self.euler.z - 90
        if (x > 180):
            x = x - 360
        return Vector3(x, self.euler.y, z)

    translation: Vector3
    """Translation vector for the 3D points to turn into the estimated face
    pose."""

    quaternion: Quaternion
    """The rotation quaternion calculated from the OpenCV rotation matrix."""

    euler: Vector3
    """The raw rotation euler angles calculated by OpenCV from the rotation
    matrix."""

    confidence: List[float]
    """How certain the tracker is for every point."""

    points: List[Vector2]
    """These are the detected face landmarks in image coordinates. There are 68
    points. The last two points are pupil points from the gaze tracker."""

    points3d: List[Vector3]
    """These are 3D points estimated form the 2D points. They should be
    rotation and translation compensated. There are 70 points with guesses for
    the eyeball center positions being added at the end of the 68 2D points."""

    open_see_features: OpenSeeFeatures
    """The facial features provided by the face tracker"""

def parse_open_see_data(packet: bytes) -> OpenSeeData:
    offset = 0
    (time,) = struct.unpack_from("d", packet, offset)
    offset += 8
    (id,) = struct.unpack_from("i", packet, offset)
    offset += 4
    camera_resolution = Vector2(*struct.unpack_from("ff", packet, offset))
    offset += 8
    (right_eye_open,) = struct.unpack_from("f", packet, offset)
    offset += 4
    (left_eye_open,) = struct.unpack_from("f", packet, offset)
    offset += 4
    (got_3d_points,) = struct.unpack_from("?", packet, offset)
    offset += 1
    (fit_3d_error,) = struct.unpack_from("f", packet, offset)
    offset += 4
    quaternion = Quaternion(*struct.unpack_from("ffff", packet, offset))
    offset += 16
    euler = Vector3(*struct.unpack_from("fff", packet, offset))
    offset += 12
    translation = Vector3(*struct.unpack_from("fff", packet, offset))
    offset += 12
    confidence = list()
    for i in range(NUMBER_OF_POINTS):
        confidence.append(*struct.unpack_from("f", packet, offset))
        offset += 4
    points = list()
    for i in range(NUMBER_OF_POINTS):
        points.append(Vector2(*struct.unpack_from("ff", packet, offset)))
        offset += 8
    points3d = list()
    for i in range(NUMBER_OF_POINTS + 2):
        points3d.append(Vector3(*struct.unpack_from("fff", packet, offset)))
        offset += 12

    (eye_left,) = struct.unpack_from("f", packet, offset)
    offset += 4
    (eye_right,) = struct.unpack_from("f", packet, offset)
    offset += 4
    (eyebrow_steepness_left,) = struct.unpack_from("f", packet, offset)
    offset += 4
    (eyebrow_up_down_left,) = struct.unpack_from("f", packet, offset)
    offset += 4
    (eyebrow_quirk_left,) = struct.unpack_from("f", packet, offset)
    offset += 4
    (eyebrow_steepness_right,) = struct.unpack_from("f", packet, offset)
    offset += 4
    (eyebrow_up_down_right,) = struct.unpack_from("f", packet, offset)
    offset += 4
    (eyebrow_quirk_right,) = struct.unpack_from("f", packet, offset)
    offset += 4
    (mouth_corner_up_down_left,) = struct.unpack_from("f", packet, offset)
    offset += 4
    (mouth_corner_in_out_left,) = struct.unpack_from("f", packet, offset)
    offset += 4
    (mouth_corner_up_down_right,) = struct.unpack_from("f", packet, offset)
    offset += 4
    (mouth_corner_in_out_right,) = struct.unpack_from("f", packet, offset)
    offset += 4
    (mouth_open,) = struct.unpack_from("f", packet, offset)
    offset += 4
    (mouth_wide,) = struct.unpack_from("f", packet, offset)

    features = OpenSeeFeatures(eye_left, eye_right, eyebrow_steepness_left,
        eyebrow_up_down_left, eyebrow_quirk_left, eyebrow_steepness_right,
        eyebrow_up_down_right, eyebrow_quirk_right, mouth_corner_up_down_left,
        mouth_corner_in_out_left, mouth_corner_up_down_right,
        mouth_corner_in_out_right, mouth_open, mouth_wide)
    
    data = OpenSeeData(time, id, camera_resolution, right_eye_open,
        left_eye_open, got_3d_points, fit_3d_error, translation,
        quaternion, euler, confidence, points, points3d, features)

    return data

