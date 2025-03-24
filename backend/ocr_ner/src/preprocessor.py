import cv2
import numpy as np
from PIL import Image


class DocumentPreprocessor:
    def __init__(self, operations=None):
        self.operations = operations or ["denoise", "threshold"]

    def process(self, image):
        img = np.array(image)
        if "denoise" in self.operations:
            img = cv2.fastNlMeansDenoisingColored(img, None, 10, 10, 7, 21)
        if "threshold" in self.operations:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        return Image.fromarray(img)
