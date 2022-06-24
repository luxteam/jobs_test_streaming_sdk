import cv2
import os
import argparse
import numpy as np

hsv_min = np.array((0, 0, 100), np.uint8)
hsv_max = np.array((0, 0, 140), np.uint8)


def suppress_qt_warnings():
    os.environ["QT_DEVICE_PIXEL_RATIO"] = "0"
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    os.environ["QT_SCREEN_SCALE_FACTORS"] = "1"
    os.environ["QT_SCALE_FACTOR"] = "1"


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", default=100000)
    parser.add_argument("--object", default="image")
    parser.add_argument("--img_path", default=os.path.abspath(os.path.join(".", "screens")))
    parser.add_argument("--vid_path", default=os.path.abspath(os.path.join(".", "videos")))
    parser.add_argument("--step", default=5)
    args = parser.parse_args()
    limit = args.limit
    img_path = args.img_path
    vid_path = args.vid_path
    obj = args.object
    step = args.step
    if obj == "image":
        path = img_path
    elif obj == "video":
        path = vid_path
    else:
        raise Exception("Unknown object type")
    return path, int(limit), obj, step


def load_images_from_folder(path):
    images = []
    for filename in os.listdir(path):
        img = cv2.imread(os.path.join(path, filename))
        if img is not None:
            images.append((img, filename))
    return images


def load_videos_from_folder(path):
    videos = []
    for filename in os.listdir(path):
        capture = cv2.VideoCapture(os.path.join(path, filename))
        if capture is not None:
            videos.append((capture, filename))
    return videos


def extract_frames(capture, step):
    count = 0
    frames = []

    while capture.isOpened():
        status, frame = capture.read()
        if status:
            frames.append(frame)
            count += int(step)
            capture.set(cv2.CAP_PROP_POS_FRAMES, count)
        else:
            capture.release()
            break
    return frames


def create_thresh(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    thresh = cv2.inRange(hsv, hsv_min, hsv_max)
    median = cv2.medianBlur(thresh, 21)
    return median


def find_contour(img, thresh, limit=100000):
    contours, hierarchy = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    max_cont = [0, 0]
    draw_contours = None
    corrupted = False
    for contour in contours:
        current = cv2.contourArea(contour, oriented = False)
        if current > limit:
            corrupted = True
            img_copy = img.copy()
            draw_contours = cv2.drawContours(img_copy, contours, -1, (0,255,0), 3)
            return corrupted, draw_contours

    img_copy = img.copy()
    draw_contours = cv2.drawContours(img_copy, contours, -1, (0,255,0), 3)
    return corrupted, draw_contours


def check_artifacts(path, limit=100000, obj_type="image", step=5):
    suppress_qt_warnings()
    if obj_type == "image":
        img = cv2.imread(path)
        thresh = create_thresh(img)
        status, contour = find_contour(img, thresh, limit)
        return status
    else:
        capture = cv2.VideoCapture(path)
        status = False
        frames = extract_frames(capture, step)
        for frame in frames:
            thresh = create_thresh(frame)
            status, contour = find_contour(frame, thresh, limit)
            if status:
                break
        return status


if __name__ == "__main__":
    suppress_qt_warnings()
    path, limit, obj, step = parse_arguments()
    if obj == "image":
        images = load_images_from_folder(path)
        for img in images:
            thresh = create_thresh(img[0])
            status, contour = find_contour(img[0], thresh, limit)
            cv2.imwrite(img[1], contour)
            print(f"%s: %s" % (img[1], status))
    else:
        videos = load_videos_from_folder(path)
        for vid in videos:
            status = False
            frames, name = extract_frames(vid, step)
            for frame in frames:
                thresh = create_thresh(frame)
                status, contour = find_contour(frame, thresh, limit)
                if status:
                    break
            print(f"%s: %s" % (name, status))
            cv2.imwrite(f"%s.jpg" % name, contour)