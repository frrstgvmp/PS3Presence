"""A software-rendering-compatible GIF item with a dark-background color key."""
from __future__ import annotations

from math import ceil

from PySide6.QtCore import Property, QRectF, QSize, Qt, QUrl, Signal
from PySide6.QtGui import QImage, QMovie, QPainter
from PySide6.QtQml import qmlRegisterType
from PySide6.QtQuick import QQuickPaintedItem


class TransparentGif(QQuickPaintedItem):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._source = QUrl()
        self._playing = False
        self._frame = QImage()
        self._clip = QRectF()
        self._cap = QRectF()
        self._movie = QMovie(self)
        self._movie.frameChanged.connect(self._refresh_frame)
        self.widthChanged.connect(self._refresh_frame)
        self.heightChanged.connect(self._refresh_frame)

    @Property(QUrl, notify=changed)
    def source(self):
        return self._source

    @source.setter
    def source(self, value):
        value = QUrl(value)
        if value == self._source:
            return
        self._movie.stop()
        self._source = value
        self._frame = QImage()
        self._movie.setFileName(value.toLocalFile())
        if not value.isEmpty():
            self._movie.jumpToFrame(0)
            self._sync_playback()
        self.update()
        self.changed.emit()

    @Property(bool, notify=changed)
    def playing(self):
        return self._playing

    @playing.setter
    def playing(self, value):
        if value == self._playing:
            return
        self._playing = value
        self._sync_playback()
        self.changed.emit()

    def _sync_playback(self):
        if self._source.isEmpty():
            return
        if self._playing:
            if self._movie.state() == QMovie.Paused:
                self._movie.setPaused(False)
            elif self._movie.state() != QMovie.Running:
                self._movie.start()
        elif self._movie.state() == QMovie.Running:
            self._movie.setPaused(True)

    @Property(int, notify=changed)
    def currentFrame(self):
        return self._movie.currentFrameNumber()

    @Property(int, notify=changed)
    def frameCount(self):
        return self._movie.frameCount()

    @Property(bool, notify=changed)
    def imageReady(self):
        return not self._frame.isNull()

    @Property(QRectF, notify=changed)
    def sourceClipRect(self):
        return self._clip

    @sourceClipRect.setter
    def sourceClipRect(self, value):
        self._clip = QRectF(value)
        self._refresh_frame()
        self.changed.emit()

    @Property(QRectF, notify=changed)
    def roundedCapRect(self):
        return self._cap

    @roundedCapRect.setter
    def roundedCapRect(self, value):
        self._cap = QRectF(value)
        self._refresh_frame()
        self.changed.emit()

    @staticmethod
    def _soften_yellow_cap(image, region, pixel_ratio):
        """Ease the tiny stepped forehead without blurring the pixel sprites."""
        rows = []
        for y in range(region.top(), region.bottom() + 1):
            yellow = []
            for x in range(region.left(), region.right() + 1):
                color = image.pixelColor(x, y)
                if color.alpha() >= 200 and color.red() >= 200 and color.green() >= 170 and color.blue() < 100:
                    yellow.append(x)
            if yellow:
                rows.append((y, min(yellow), max(yellow)))
        if not rows:
            return
        top, left, right = rows[0]
        for below, wider_left, wider_right in rows[1:]:
            padding = min(ceil(2 * pixel_ratio), left - wider_left, wider_right - right)
            if padding > 0:
                color = image.pixelColor((left + right) // 2, top)
                painter = QPainter(image)
                painter.setCompositionMode(QPainter.CompositionMode_Source)
                for distance in range(1, padding + 1):
                    # A solid inner pixel and a softer outer edge keep the
                    # small dome round on both dark and light themes.
                    color.setAlpha(round(255 * (padding - distance + 1) / padding))
                    painter.fillRect(left - distance, top, 1, below - top, color)
                    painter.fillRect(right + distance, top, 1, below - top, color)
                painter.end()
                return

    def _refresh_frame(self, *_):
        image = self._movie.currentImage()
        if image.isNull() or self._source.isEmpty():
            return
        bounds = self._clip.toRect().intersected(image.rect()) if not self._clip.isEmpty() else image.rect()
        image = image.copy(bounds)
        # Process only the small displayed frame, not the full-resolution GIF.
        ratio = self.window().devicePixelRatio() if self.window() else 1.0
        size = QSize(max(1, ceil(self.width() * ratio)), max(1, ceil(self.height() * ratio)))
        image = image.scaled(size, Qt.KeepAspectRatio, Qt.FastTransformation)
        image = image.convertToFormat(QImage.Format_RGBA8888)
        pixels = image.bits().cast("B")
        for offset in range(0, image.sizeInBytes(), 4):
            if max(pixels[offset], pixels[offset + 1], pixels[offset + 2]) <= 32:
                pixels[offset + 3] = 0
        del pixels
        if not self._cap.isEmpty() and bounds.width() and bounds.height():
            sx, sy = image.width() / bounds.width(), image.height() / bounds.height()
            region = QRectF((self._cap.x() - bounds.x()) * sx, (self._cap.y() - bounds.y()) * sy,
                            self._cap.width() * sx, self._cap.height() * sy).toAlignedRect().intersected(image.rect())
            self._soften_yellow_cap(image, region, ratio)
        self._frame = image
        self.update()
        self.changed.emit()

    def paint(self, painter: QPainter):
        if not self._frame.isNull():
            painter.drawImage(self.boundingRect(), self._frame)


qmlRegisterType(TransparentGif, "Presence.Animation", 1, 0, "TransparentGif")
