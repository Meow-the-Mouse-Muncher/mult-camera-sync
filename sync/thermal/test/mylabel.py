from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from camera_inf import *


class MyLabel(QLabel):
    def __init__(self, parent=None):
        super(MyLabel, self).__init__(parent)
        self.isShow = False
        self.isValid = False  # 是否有数据
        self.imgw = WIDTH
        self.imgh = HEIGHT
        self.setMouseTracking(True)
        self.mousePt = QPoint()
        self.realPt = QPoint()
        self.realPtTemp = 0
        self.dis_width = 0      # 图像显示的真实宽度,label宽高比跟图像不一致
        self.dis_woffset = 0    # 图像显示的真实偏移,label宽高比跟图像不一致
        self.dis_height = 0      # 图像显示的真实宽度,label宽高比跟图像不一致
        self.dis_hoffset = 0    # 图像显示的真实偏移,label宽高比跟图像不一致
        self.sframe = []
        if self.width()/self.imgw >= self.height()/self.imgh:
            self.dis_width = self.imgw * self.height() / self.imgh  # 图像显示的真实宽度,
            self.dis_woffset = (self.width() - self.dis_width) / 2  # 图像显示的真实偏移,
            self.dis_height = self.height()
            self.dis_hoffset = 0
        else:
            self.dis_width = self.width()
            self.dis_woffset = 0
            self.dis_height = self.imgh * self.width() / self.imgw  # 图像显示的真实宽度,
            self.dis_hoffset = (self.height() - self.dis_height) / 2  # 图像显示的真实偏移,

        # 最多支持MAX_POINT个点
        self.PointArray = []
        for i in range(0, MAX_POINT):
            self.PointArray.append(STAT_POINT())


    def set_show(self, s):
        self.isShow = s

    def show_img(self, rgb, frame, img_size):  # bgr
        self.imgw = img_size[1]
        self.imgh = img_size[0]
        size = QSize(self.size().width(), self.size().height())
        qImg = QImage(rgb, self.imgw, self.imgh, QImage.Format_BGR888)
        pixmap = QPixmap.fromImage(qImg).scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.setPixmap(pixmap)
        self.sframe = frame
        self.isValid = True
        self.update()

    def get_realpos(self, pt):  # 光标在图像中的坐标
        realpt = QPoint()
        realpt.setX(int((pt.x() - self.dis_woffset) * self.imgw / self.dis_width))
        realpt.setY(int((pt.y() - self.dis_hoffset) * self.imgh / self.dis_height))
        return realpt

    def resizeEvent(self, event):
        if self.width()/self.imgw >= self.height()/self.imgh:
            self.dis_width = self.imgw * self.height() / self.imgh  # 图像显示的真实宽度,
            self.dis_woffset = (self.width() - self.dis_width) / 2  # 图像显示的真实偏移,
            self.dis_height = self.height()
            self.dis_hoffset = 0
        else:
            self.dis_width = self.width()
            self.dis_woffset = 0
            self.dis_height = self.imgh * self.width() / self.imgw  # 图像显示的真实宽度,
            self.dis_hoffset = (self.height() - self.dis_height) / 2  # 图像显示的真实偏移,

    def mouseMoveEvent(self, event):
        QLabel.mouseMoveEvent(self, event)
        x = event.x()
        y = event.y()
        self.mousePt.setX(x)
        self.mousePt.setY(y)
        self.realPt = self.get_realpos(self.mousePt)

    def enterEvent(self, event):
        if self.isValid:
            self.set_show(True)

    def leaveEvent(self, event):
        self.set_show(False)

    def paintEvent(self, event):
        super().paintEvent(event)

        if self.isShow:
            painter = QPainter(self)
            painter.begin(self)
            brush = QBrush(QColor(128, 128, 128, 180))
            pen = QPen(QColor(128, 128, 128, 180))
            font = QFont("Microsoft YaHei", 10, 60)
            painter.setPen(pen)
            painter.setBrush(brush)
            painter.setFont(font)

            if 0 <= self.realPt.y() < self.imgh and 0 <= self.realPt.x() < self.imgw:
                self.realPtTemp = get_pt_temp(self.sframe, self.realPt.x(), self.realPt.y())

                ###  调用获取点温度sdk示例
                self.PointArray[0].sPoint.x = self.realPt.x()
                self.PointArray[0].sPoint.y = self.realPt.y()
                self.PointArray[0].inputEmiss = 0.98
                self.PointArray[0].inputReflect = 25.0
                self.PointArray[0].inputDis = 2.0
                get_point_temp(self.sframe, self.PointArray[0])
                # print('temp=%.1f,  x=%d, y=%d' % (self.PointArray[0].sTemp.maxTemper, self.PointArray[0].sTemp.maxTemperPT.x, self.PointArray[0].sTemp.maxTemperPT.y))


            text = str(self.realPtTemp) + "℃" + " (" + str(self.realPt.x()) + "," + str(self.realPt.y()) + ")"

            qfm = painter.fontMetrics()
            text_width = qfm.width(text)
            text_height = qfm.height()
            text_rect = QRect(self.mousePt.x(), self.mousePt.y(), text_width, text_height)

            if self.mousePt.x() < self.width() / 2:
                text_rect.translate(20, 0)
            else:
                text_rect.translate(-text_width - 20, 0)

            if self.mousePt.y() < self.height() / 2:
                text_rect.translate(0, text_height)
            else:
                text_rect.translate(0, -20)

            painter.drawRect(text_rect)
            painter.setPen(QPen(Qt.white))
            painter.drawText(text_rect, Qt.AlignLeft, text)
            painter.end()


