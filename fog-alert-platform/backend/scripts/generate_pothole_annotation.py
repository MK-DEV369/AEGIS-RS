from pathlib import Path
import sys
repo=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(repo/'backend'))
try:
    from fog_api.services import fog_predictor
    import cv2
    img_path=repo/'potholetest.jpg'
    if not img_path.exists():
        print('MISSING_IMAGE', img_path)
        raise SystemExit(1)
    bgr = cv2.imread(str(img_path))
    h,w = bgr.shape[:2]
    x1 = w*0.3
    y1 = h*0.4
    x2 = w*0.7
    y2 = h*0.8
    detections = {
        'items': [
            {
                'class_id': 0,
                'class_name': 'pothole',
                'confidence': 0.92,
                'bbox_xyxy': [x1, y1, x2, y2]
            }
        ],
        'count': 1,
        'max_risk': 0.75,
        'critical_count': 0,
        'high_count': 1,
    }
    enhanced = fog_predictor._enhance_pothole_frame(bgr.copy(), detections, coordinates={'lat':12.34,'lng':56.78})
    out_path = repo/'potholetest_annotated_generated.jpg'
    ok = cv2.imwrite(str(out_path), enhanced)
    if ok:
        print('SAVED', out_path)
    else:
        print('FAILED_TO_SAVE')
except Exception as e:
    print('ERROR', e)
