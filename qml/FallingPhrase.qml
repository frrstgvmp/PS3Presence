import QtQuick

// Native animation clocks drive a small group of text glyphs. No timers,
// canvas redraws or external assets; both stop when About is hidden.
Item {
    id: phrase
    property string text: ""
    property color color: "white"
    property font textFont: Qt.font({ family: "Segoe UI", pixelSize: 11 })
    property bool active: false
    property real elapsed: 0
    property int cycle: 0
    property bool bursting: false
    property real burstElapsed: 0
    property int burstSerial: 0
    readonly property bool animating: timeline.running || burstAnimation.running
    readonly property int letterCount: letters.count
    readonly property string phase: bursting ? "bursting" : elapsed < 2000 ? "falling"
        : elapsed < 5800 ? "assembled" : elapsed < 7600 ? "scattering" : "waiting"
    implicitWidth: fullMetrics.advanceWidth
    implicitHeight: 26

    function noise(index, salt) {
        var value = Math.sin((index + 1) * 127.1 + salt * 311.7 + cycle * 78.23) * 43758.5453
        return value - Math.floor(value)
    }
    function clamp(value) { return Math.max(0, Math.min(1, value)) }
    function burst() {
        if (!active)
            return
        // Capture the current pose, including a partially completed fall or burst.
        for (var i = 0; i < letters.count; ++i) {
            var letter = letters.itemAt(i)
            letter.burstX = letter.x
            letter.burstY = letter.y
            letter.burstRotation = letter.rotation
            letter.burstOpacity = letter.opacity
        }
        burstSerial += 1
        burstElapsed = 0
        bursting = true
        burstAnimation.restart()
    }
    onActiveChanged: {
        if (!active) {
            burstAnimation.stop()
            bursting = false
            burstElapsed = 0
            burstSerial = 0
            elapsed = 0
            cycle = 0
        }
    }

    TextMetrics { id: fullMetrics; text: phrase.text; font: phrase.textFont }
    Item {
        // Leave room above and below the baseline without moving the contact row.
        x: -64; y: -64; width: phrase.width + 128; height: phrase.height + 128
        clip: true
        Repeater {
            id: letters
            model: phrase.text.length
            delegate: Text {
                id: letter
                required property int index
                objectName: "sunPraiseLetter" + index
                text: phrase.text.charAt(index)
                font: phrase.textFont; color: phrase.color
                readonly property real homeX: prefixMetrics.advanceWidth + 64
                readonly property real homeY: 64 + (phrase.height - height) / 2
                property real burstX: 0
                property real burstY: 0
                property real burstRotation: 0
                property real burstOpacity: 0
                readonly property real burstTime: phrase.burstElapsed / 1000
                readonly property real burstAngle: phrase.noise(index, 10 + phrase.burstSerial) * Math.PI * 2
                readonly property real burstSpeed: 65 + phrase.noise(index, 20 + phrase.burstSerial) * 45
                readonly property real fallDelay: phrase.noise(index, 1) * 850
                readonly property real fallDuration: 550 + phrase.noise(index, 2) * 450
                readonly property real fall: phrase.clamp((phrase.elapsed - fallDelay) / fallDuration)
                readonly property real settle: phrase.clamp((phrase.elapsed - fallDelay - fallDuration) / 170)
                readonly property real scatter: phrase.clamp((phrase.elapsed - 5800 - phrase.noise(index, 3) * 480)
                    / (650 + phrase.noise(index, 4) * 450))
                readonly property real fade: phrase.clamp((scatter - 0.2) / 0.8)
                x: phrase.bursting ? burstX + Math.cos(burstAngle) * burstSpeed * burstTime
                    : homeX + (1 - fall) * (phrase.noise(index, 5) * 8 - 4)
                    + scatter * scatter * (phrase.noise(index, 6) * 20 - 10)
                y: phrase.bursting ? burstY + Math.sin(burstAngle) * burstSpeed * burstTime + 50 * burstTime * burstTime
                    : homeY - (1 - fall * fall) * (30 + phrase.noise(index, 7) * 20)
                    + Math.sin(settle * Math.PI) * (1 - settle) * 4
                    + scatter * scatter * 58
                rotation: phrase.bursting ? burstRotation + (phrase.noise(index, 30 + phrase.burstSerial) * 400 - 200) * burstTime
                    : (1 - fall) * (phrase.noise(index, 8) * 40 - 20)
                    + scatter * (phrase.noise(index, 9) * 150 - 75)
                opacity: phrase.bursting ? burstOpacity * (1 - phrase.clamp((phrase.burstElapsed - 150) / 750))
                    : phrase.elapsed < fallDelay ? 0
                    : Math.min(1, fall * 5) * (1 - fade * fade * (3 - 2 * fade))
                transformOrigin: Item.Center
                TextMetrics {
                    id: prefixMetrics
                    text: phrase.text.substring(0, letter.index); font: phrase.textFont
                }
            }
        }
    }
    MouseArea {
        objectName: "sunPraiseClickTarget"
        anchors.fill: parent
        enabled: phrase.active
        onClicked: phrase.burst()
    }
    NumberAnimation {
        id: burstAnimation
        objectName: "sunPraiseBurstAnimation"
        target: phrase; property: "burstElapsed"
        from: 0; to: 900; duration: 900
        onFinished: {
            phrase.bursting = false
            phrase.elapsed = 0
            phrase.cycle += 1
            timeline.restart()
        }
    }
    SequentialAnimation {
        id: timeline
        objectName: "sunPraiseTimeline"
        running: phrase.active; loops: Animation.Infinite
        paused: phrase.bursting
        NumberAnimation { target: phrase; property: "elapsed"; from: 0; to: 8600; duration: 8600 }
        ScriptAction { script: phrase.cycle += 1 }
    }
}
