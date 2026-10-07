import QtQuick
import QtQuick.Controls

Item {
    id: avatar
    property url source
    property string initials: "?"
    property color backgroundColor
    property color textColor
    property color borderColor
    readonly property bool imageReady: avatarImage.status === Image.Ready && picture.ready
    implicitWidth: 56; implicitHeight: 56
    Image {
        id: avatarImage
        objectName: "avatarSourceImage"
        source: avatar.source
        visible: false
        asynchronous: true
        autoTransform: true
        cache: true
        onStatusChanged: picture.requestPaint()
    }
    Rectangle {
        anchors.fill: parent; radius: width / 2
        color: avatar.backgroundColor
        Label {
            anchors.centerIn: parent
            text: avatar.initials
            font.pixelSize: 22; font.weight: Font.DemiBold
            color: avatar.textColor
            visible: !avatar.imageReady
        }
    }
    Canvas {
        id: picture
        objectName: "avatarPicture"
        property bool ready: false
        property bool completed: false
        property url imageSource: avatar.source
        property url cachedSource: ""
        function reload() {
            ready = false
            if (cachedSource.toString() !== "") unloadImage(cachedSource)
            cachedSource = imageSource
            if (imageSource.toString() !== "") {
                loadImage(imageSource)
                ready = isImageLoaded(imageSource)
            }
            requestPaint()
        }
        onImageSourceChanged: { if (completed) reload() }
        Component.onCompleted: { completed = true; reload() }
        onImageLoaded: { ready = isImageLoaded(imageSource); requestPaint() }
        // Render at 2x, then filter down once. The round mask retains fine
        // detail and smooth edges even with the app's fractional UI scale.
        width: avatar.width * 2; height: avatar.height * 2
        scale: 0.5; transformOrigin: Item.TopLeft
        smooth: true
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            var ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            if (!avatar.imageReady) return
            ctx.save()
            ctx.beginPath()
            ctx.arc(width / 2, height / 2, Math.min(width, height) / 2 - 2, 0, Math.PI * 2)
            ctx.clip()
            // Centre-crop instead of stretching a non-square PSN image.
            var iw = avatarImage.implicitWidth
            var ih = avatarImage.implicitHeight
            var side = Math.min(iw, ih)
            if (side > 0)
                ctx.drawImage(avatar.source, (iw - side) / 2, (ih - side) / 2, side, side, 0, 0, width, height)
            ctx.restore()
        }
    }
    Rectangle {
        anchors.fill: parent; radius: width / 2
        color: "transparent"; border.width: 1; border.color: avatar.borderColor
    }
}
