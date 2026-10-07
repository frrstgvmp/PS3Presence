import QtQuick

// Reuse the illustrated fan leaf from the frame, rather than redraw it.
// Native Image transforms share a cached cropped texture; no full-window
// Canvas uploads, shaders, extra assets, or mouse handlers are needed.
Item {
    id: foliage
    property bool active: false
    property bool renderingEnabled: true
    property real intensity: active ? 1 : 0
    property real elapsed: 0
    property double lastFrame: 0
    readonly property int particleCount: leafRepeater.count
    readonly property bool animating: movement.running
    visible: intensity > 0.001
    opacity: intensity
    clip: true

    Behavior on intensity {
        NumberAnimation { duration: foliage.active ? 1100 : 700; easing.type: Easing.InOutSine }
    }

    Repeater {
        id: leafRepeater
        model: foliage.active || foliage.intensity > 0.001 ? 28 : 0
        delegate: Image {
            id: leaf
            objectName: "fallingCannabisLeaf" + index
            readonly property real depth: Math.random()
            readonly property real phase: Math.random() * Math.PI * 2
            readonly property real fallSpeed: 26 + depth * 30
            readonly property real spinSpeed: (index % 2 ? 1 : -1) * (8 + depth * 16)
            readonly property bool imageReady: status === Image.Ready
            width: 12 + depth * 18
            height: width * 85 / 126
            source: "../assets/botanical-cannabis-theme.png"
            sourceClipRect: Qt.rect(1410, 928, 126, 85)
            asynchronous: true; cache: true; smooth: true; mipmap: true
            opacity: 0.35 + depth * 0.45
            transformOrigin: Item.Center
            transform: Scale {
                origin.x: leaf.width / 2; origin.y: leaf.height / 2
                // Gentle tumbling without vanishing or flipping abruptly.
                xScale: 0.68 + 0.32 * Math.sin(foliage.elapsed * 0.8 + leaf.phase)
            }
            Component.onCompleted: {
                x = Math.random() * Math.max(0, foliage.width - width)
                y = index < 8 ? -height - Math.random() * 35 : -height - Math.random() * foliage.height
                rotation = Math.random() * 360
            }
        }
    }

    Timer {
        id: movement
        interval: 33; repeat: true
        running: foliage.visible && foliage.renderingEnabled && foliage.particleCount > 0
        onRunningChanged: foliage.lastFrame = 0
        onTriggered: {
            var now = Date.now()
            var dt = foliage.lastFrame ? Math.min((now - foliage.lastFrame) / 1000, 0.05) : 0.033
            foliage.lastFrame = now
            foliage.elapsed += dt
            for (var i = 0; i < leafRepeater.count; ++i) {
                var leaf = leafRepeater.itemAt(i)
                if (leaf === null) continue
                leaf.y += leaf.fallSpeed * dt
                leaf.x += Math.sin(foliage.elapsed * 0.6 + leaf.phase) * (12 + leaf.depth * 14) * dt
                leaf.rotation += leaf.spinSpeed * dt
                if (leaf.y > foliage.height + leaf.width) {
                    leaf.y = -leaf.width - Math.random() * 45
                    leaf.x = Math.random() * Math.max(0, foliage.width - leaf.width)
                }
                if (leaf.x > foliage.width + leaf.width) leaf.x = -leaf.width
                if (leaf.x < -leaf.width) leaf.x = foliage.width + leaf.width
            }
        }
    }
}
