from paddleocr import PaddleOCR
import cv2
import numpy as np

# 只使用检测模型
# ocr_det = PaddleOCR(use_angle_cls=True, device='cpu', lang='ch')
ocr = PaddleOCR(use_angle_cls=True, lang="ch", det_db_thresh=0.5)


def text_detection_only(image_path):
    result = ocr.predict(image_path)
    
    # 可视化检测结果
    image = cv2.imread(image_path)
    
    # for page in result:
    #     for coord, (txt, score) in page:
    #         print(txt, score)
    if result is not None:
        points = []
        print(len(result))
        for res in result:
            if res:
                for (rec_texts, dt_polys) in zip(res['rec_texts'], res['dt_polys']):
                    print(rec_texts, dt_polys)
                    # 获取检测框坐标
                    if rec_texts == '兑换比例':
                        points.append(np.array(dt_polys, dtype=np.int32))
                    
                    # 绘制检测框（绿色）
                cv2.polylines(image, [points], True, (0, 255, 0), 2)
    
    cv2.imshow('Detection Result', image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    
img = r"C:\Poetools\PathofAutoV2\faust\QQ20251129-125525.png"
text_detection_only(img)