import QtQuick

// Decorative only: no input handlers, so the controls and bulbs stay clickable.
Item {
    id: snow
    property bool active: false
    property bool renderingEnabled: true
    property real intensity: active ? 1 : 0
    property var flakes: []
    property real elapsed: 0
    property double lastFrame: 0
    visible: intensity > 0.001
    opacity: intensity
    clip: true

    Behavior on intensity {
        NumberAnimation { duration: snow.active ? 1400 : 900; easing.type: Easing.InOutSine }
    }
    onActiveChanged: {
        if (active && flakes.length === 0)
            initialize()
    }
    function initialize() {
        var particles = []
        for (var i = 0; i < 58; ++i) {
            var depth = Math.random()
            particles.push({
                x: Math.random() * width,
                y: i < 8 ? -Math.random() * 50 : -Math.random() * height,
                radius: 0.7 + depth * 2.3,
                speed: 22 + depth * 42,
                phase: Math.random() * Math.PI * 2,
                depth: depth
            })
        }
        flakes = particles
        lastFrame = 0
    }
    Timer {
        interval: 33; repeat: true
        running: snow.visible && snow.renderingEnabled
        onRunningChanged: snow.lastFrame = 0
        onTriggered: {
            var now = Date.now()
            var dt = snow.lastFrame ? Math.min((now - snow.lastFrame) / 1000, 0.05) : 0.033
            snow.lastFrame = now
            snow.elapsed += dt
            for (var i = 0; i < snow.flakes.length; ++i) {
                var flake = snow.flakes[i]
                flake.y += flake.speed * dt
                flake.x += (5 + Math.sin(snow.elapsed * 0.65 + flake.phase) * (8 + flake.depth * 12)) * dt
                if (flake.y > snow.height + 12) {
                    flake.y = -12 - Math.random() * 70
                    flake.x = Math.random() * snow.width
                }
                if (flake.x > snow.width + 12) flake.x = -12
                if (flake.x < -12) flake.x = snow.width + 12
            }
            snowfallCanvas.requestPaint()
        }
    }
    Canvas {
        id: snowfallCanvas
        anchors.fill: parent
        onPaint: {
            var ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            for (var i = 0; i < snow.flakes.length; ++i) {
                var f = snow.flakes[i]
                if (f.y < -12 || f.y > height + 12) continue
                var alpha = 0.22 + f.depth * 0.40
                var glow = ctx.createRadialGradient(f.x, f.y, 0, f.x, f.y, f.radius * 3)
                glow.addColorStop(0, "rgba(222, 239, 255, " + alpha * 0.32 + ")")
                glow.addColorStop(1, "rgba(222, 239, 255, 0)")
                ctx.fillStyle = glow
                ctx.fillRect(f.x - f.radius * 3, f.y - f.radius * 3, f.radius * 6, f.radius * 6)
                // The closest crystals rotate gently; distant flakes are soft dots.
                ctx.fillStyle = f.y < 150 ? "rgba(255, 245, 222, " + alpha + ")" : "rgba(235, 247, 255, " + alpha + ")"
                if (f.depth > 0.82) {
                    ctx.save()
                    ctx.translate(f.x, f.y)
                    ctx.rotate(f.phase + snow.elapsed * 0.12)
                    ctx.strokeStyle = ctx.fillStyle
                    ctx.lineWidth = 0.65
                    ctx.beginPath()
                    for (var arm = 0; arm < 6; ++arm) {
                        var angle = arm * Math.PI / 3
                        ctx.moveTo(0, 0)
                        ctx.lineTo(Math.cos(angle) * f.radius * 1.4, Math.sin(angle) * f.radius * 1.4)
                    }
                    ctx.stroke()
                    ctx.restore()
                } else {
                    ctx.beginPath()
                    ctx.arc(f.x, f.y, f.radius * 0.65, 0, Math.PI * 2)
                    ctx.fill()
                }
            }
        }
    }
}
