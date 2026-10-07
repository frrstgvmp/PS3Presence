import QtQuick

Item {
    id: indicator
    property color color: "#94a3b8"
    property string mode: "offline"
    property bool active: true
    property real pulse: 0
    readonly property bool connecting: mode === "connecting"
    readonly property bool online: mode === "online"
    readonly property bool animating: breathing.running
    readonly property int pulseDuration: connecting ? 1100 : 3600
    readonly property real breath: (1 - Math.cos(pulse * Math.PI * 2)) / 2
    implicitWidth: 18; implicitHeight: 18
    onActiveChanged: { if (!active) pulse = 0 }

    Rectangle {
        anchors.centerIn: parent
        width: indicator.connecting ? 6 + 11 * indicator.pulse : 9 + 6 * indicator.pulse
        height: width; radius: width / 2
        color: "transparent"; border.color: indicator.color; border.width: 1
        opacity: !indicator.active || (!indicator.connecting && !indicator.online) ? 0
            : (indicator.connecting ? 0.4 : 0.12) * (1 - indicator.pulse)
    }
    Rectangle {
        anchors.centerIn: parent
        width: 10; height: 10; radius: 5; color: indicator.color
        opacity: indicator.connecting ? 0.05 + indicator.breath * 0.12
            : indicator.online ? 0.04 + indicator.breath * 0.04 : 0
    }
    Rectangle {
        objectName: "connectionIndicatorDot"
        anchors.centerIn: parent
        width: 6; height: 6; radius: 3; color: indicator.color
        scale: indicator.connecting ? 0.82 + indicator.breath * 0.28
            : indicator.online ? 0.96 + indicator.breath * 0.07 : 1
        opacity: indicator.connecting ? 0.4 + indicator.breath * 0.6
            : indicator.online ? 0.82 + indicator.breath * 0.18 : 0.9
    }
    NumberAnimation {
        id: breathing
        target: indicator; property: "pulse"; from: 0; to: 1
        duration: indicator.pulseDuration; loops: Animation.Infinite
        running: indicator.active && (indicator.connecting || indicator.online)
    }
}
