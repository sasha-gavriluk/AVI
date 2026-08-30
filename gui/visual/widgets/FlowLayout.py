from PyQt6.QtWidgets import QLayout, QSizePolicy, QStyle
from utils.OtherUtils import _handle_error
from PyQt6.QtCore import QPoint, QRect, QSize, Qt

class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=-1, hSpacing=-1, vSpacing=-1):
        super().__init__(parent)
        self._itemList = []
        self.m_hSpace = hSpacing
        self.m_vSpace = vSpacing
        if margin > 0:
            self.setContentsMargins(margin, margin, margin, margin)

    @_handle_error
    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    @_handle_error
    def addItem(self, item):
        self._itemList.append(item)

    @_handle_error
    def horizontalSpacing(self):
        if self.m_hSpace >= 0:
            return self.m_hSpace
        else:
            return self.smartSpacing(QStyle.PixelMetric.PM_LayoutHorizontalSpacing)

    @_handle_error
    def verticalSpacing(self):
        if self.m_vSpace >= 0:
            return self.m_vSpace
        else:
            return self.smartSpacing(QStyle.PixelMetric.PM_LayoutVerticalSpacing)

    @_handle_error
    def count(self):
        return len(self._itemList)

    @_handle_error
    def itemAt(self, index):
        if 0 <= index < len(self._itemList):
            return self._itemList[index]
        return None

    @_handle_error
    def takeAt(self, index):
        if 0 <= index < len(self._itemList):
            return self._itemList.pop(index)
        return None

    @_handle_error
    def expandingDirections(self):
        return Qt.Orientation(0)

    @_handle_error
    def hasHeightForWidth(self):
        return True

    @_handle_error
    def heightForWidth(self, width):
        return self.doLayout(QRect(0, 0, width, 0), True)

    @_handle_error
    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect, False)

    @_handle_error
    def sizeHint(self):
        return self.minimumSize()

    @_handle_error
    def minimumSize(self):
        size = QSize()
        for item in self._itemList:
            size = size.expandedTo(item.minimumSize())
        left, top, right, bottom = self.getContentsMargins()
        size += QSize(left + right, top + bottom)
        return size

    @_handle_error
    def smartSpacing(self, pm):
        parent = self.parent()
        if not parent:
            return -1
        elif parent.isWidgetType():
            return parent.style().pixelMetric(pm, None, parent)
        else:
            return parent.spacing()

    @_handle_error
    def doLayout(self, rect, testOnly):
        left, top, right, bottom = self.getContentsMargins()
        effectiveRect = rect.adjusted(+left, +top, -right, -bottom)
        x = effectiveRect.x()
        y = effectiveRect.y()
        lineHeight = 0

        for item in self._itemList:
            wid = item.widget()
            spaceX = self.horizontalSpacing()
            if spaceX == -1:
                spaceX = wid.style().layoutSpacing(QSizePolicy.ControlType.PushButton, QSizePolicy.ControlType.PushButton, Qt.Orientation.Horizontal)
            spaceY = self.verticalSpacing()
            if spaceY == -1:
                spaceY = wid.style().layoutSpacing(QSizePolicy.ControlType.PushButton, QSizePolicy.ControlType.PushButton, Qt.Orientation.Vertical)

            nextX = x + item.sizeHint().width() + spaceX
            if nextX - spaceX > effectiveRect.right() and lineHeight > 0:
                x = effectiveRect.x()
                y = y + lineHeight + spaceY
                nextX = x + item.sizeHint().width() + spaceX
                lineHeight = 0

            if not testOnly:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = nextX
            lineHeight = max(lineHeight, item.sizeHint().height())

        return y + lineHeight - rect.y() + bottom
