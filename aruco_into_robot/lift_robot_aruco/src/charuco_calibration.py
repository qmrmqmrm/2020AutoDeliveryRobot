#!/usr/bin/env python
import cv2
import glob
import os
import math
import numpy as np
import picamera
from cv2 import aruco
import rospy
from multi_robot.msg import aruco_msgs
from multi_robot.msg import check_msg

aruco_dict = aruco.Dictionary_get(aruco.DICT_6X6_250)
board = aruco.CharucoBoard_create(7, 5, 1, .8, aruco_dict)
"""
aruco 마커 검출 노드
"""


# 미리 찍어놓은 이미지 (camera_cla_img)를 가지고 왜곡률 등을 계산하는 함수
def cal():
    """
    Charuco base pose estimation.
    """
    rospy.loginfo("POSE ESTIMATION STARTS:")

    allCorners = []
    allIds = []
    decimator = 0
    # SUB PIXEL CORNER DETECTION CRITERION
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.00001)
    images = glob.glob('/home/pi/catkin_ws/src/2020AutoDeliveryRobot/multi_robot/src/camera_cal_img/cal*.png')
    for im in images:
        print("=> Processing image {0}".format(im))
        frame = cv2.imread(im)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, rejectedImgPoints = cv2.aruco.detectMarkers(gray, aruco_dict)

        if len(corners) > 0:
            # SUB PIXEL DETECTION
            for corner in corners:
                cv2.cornerSubPix(gray, corner,
                                 winSize=(3, 3),
                                 zeroZone=(-1, -1),
                                 criteria=criteria)
            res2 = cv2.aruco.interpolateCornersCharuco(corners, ids, gray, board)
            if res2[1] is not None and res2[2] is not None and len(res2[1]) > 3 and decimator % 1 == 0:
                allCorners.append(res2[1])
                allIds.append(res2[2])

        decimator += 1

    imsize = gray.shape
    return allCorners, allIds, imsize


#  charuco calibration 함수
def calibrate_charuco(allCorners, allIds, imsize):
    """
    Calibrates the camera using the dected corners.
    """
    rospy.loginfo("CAMERA CALIBRATION")

    cameraMatrixInit = np.array([[249.5, 0., imsize[1] / 2.],
                                 [0., 249.5, imsize[0] / 2.],
                                 [0., 0., 1.]])

    distCoeffsInit = np.zeros((5, 1))
    flags = (cv2.CALIB_USE_INTRINSIC_GUESS + cv2.CALIB_RATIONAL_MODEL + cv2.CALIB_FIX_ASPECT_RATIO)
    # flags = (cv2.CALIB_RATIONAL_MODEL)
    (ret, camera_matrix, distortion_coefficients0,
     rotation_vectors, translation_vectors,
     stdDeviationsIntrinsics, stdDeviationsExtrinsics,
     perViewErrors) = cv2.aruco.calibrateCameraCharucoExtended(
        charucoCorners=allCorners,
        charucoIds=allIds,
        board=board,
        imageSize=imsize,
        cameraMatrix=cameraMatrixInit,
        distCoeffs=distCoeffsInit,
        flags=flags,
        criteria=(cv2.TERM_CRITERIA_EPS & cv2.TERM_CRITERIA_COUNT, 10000, 1e-9))
    rospy.loginfo("END CALIBRATION")
    return ret, camera_matrix, distortion_coefficients0, rotation_vectors, translation_vectors


# marker 검출 함수
def detect_marker(mtx, dist):
    rospy.loginfo("START DETECT MARKER")
    os.system('sudo modprobe bcm2835-v4l2')
    cam = cv2.VideoCapture(-1)
    # cam = picamera.PiCamera()
    # cam.resolution=(720, 480)
    # cam.framerate = 30
    param = cv2.aruco.DetectorParameters_create()
    aruco_pub = rospy.Publisher('aruco_msg', aruco_msgs, queue_size=10)
    check_pub = rospy.Publisher('check_aruco', check_msg, queue_size=10)
    aruco = aruco_msgs()
    check = check_msg()
    if cam.isOpened():
        while not rospy.is_shutdown():
            _, frame = cam.read()
            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            coners, ids, point = cv2.aruco.detectMarkers(gray_frame, aruco_dict, parameters=param)
            if np.all(ids != None):
                if ids[0] == 2:
                    check.check = True
                    if check.check == True:
                        rvecs, tvecs, objpoint = cv2.aruco.estimatePoseSingleMarkers(coners, 0.04, mtx, dist)
                        frame = cv2.aruco.drawAxis(frame, mtx, dist, rvecs[0], tvecs[0], 0.04)
                        rvecs_msg = rvecs.tolist()
                        tvecs_msg = tvecs.tolist()
                        rvecs_msg_x = rvecs_msg[0][0][0]
                        rvecs_msg_y = rvecs_msg[0][0][1]
                        rvecs_msg_z = rvecs_msg[0][0][2]
                        tvecs_msg_x = tvecs_msg[0][0][0]
                        tvecs_msg_y = tvecs_msg[0][0][1]
                        tvecs_msg_z = tvecs_msg[0][0][2]
                        aruco.r_x = rvecs_msg_x
                        aruco.r_y = rvecs_msg_y
                        aruco.r_z = rvecs_msg_z
                        aruco.t_x = tvecs_msg_x
                        aruco.t_y = tvecs_msg_y
                        aruco.t_z = tvecs_msg_z
                        aruco.id = int(ids[0])
                        aruco_pub.publish(aruco)

            else:
                check.check = False

            check_pub.publish(check)
            rospy.loginfo(check)
            #        frame = cv2.aruco.drawDetectedMarkers(frame, coners, ids)
            #        cv2.imshow("result", frame)
            k = cv2.waitKey(30)
    #        if k == ord('q'):
    #            break
    cam.release()
    # cv2.destroyAllWindows()


def main():
    rospy.init_node("aruco_detect")
    allCorners, allIds, imsize = cal()
    print("Calibration is Completed. Starting tracking marker.")
    ret, mtx, dist, rvec, tvec = calibrate_charuco(allCorners, allIds, imsize)
    detect_marker(mtx, dist)


if __name__ == "__main__":
    main()
