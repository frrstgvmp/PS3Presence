import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import Presence.Animation 1.0

ApplicationWindow {
    id: root
    function tr(text) { return presence.language === "en" ? presence.translate(text) : text }
    property real uiScale: 1.0
    readonly property real artScale: width / 680
    readonly property real artTop: dashboard.y + toolbarDivider.y
    property bool decorationsEnabled: false
    onDecorationsEnabledChanged: {
        if (!decorationsEnabled) {
            setAllLights(false)
            festiveAtmosphereActive = false
            allLightsSecretActive = false
            secretLeafClicks = 0
            updateMusicalHover(null)
        }
    }
    property var themes: [
        { id: "light", name: "Роса", swatch: "#f3f0e8", background: "#edf2ee", surface: "#fbfdfb", dialog: "#ffffff", tile: "#dfeae6", border: "#a9c0b9", accent: "#39796e", accentPressed: "#2d6259", button: "#d5e5df", buttonPressed: "#bfd4cc", buttonText: "#203d36", buttonBorder: "#88aaa0", secondary: "#f2f6f4", secondaryPressed: "#e0eae6", text: "#17211f", muted: "#66766f", soft: "#405a52", logBg: "#f7faf8", logText: "#294b44", fieldBg: "#f4f7f5", divider: "#cfddd7", accentBorder: "#39796e", artOpacity: 0.16 },
        { id: "oled", name: "OLED", swatch: "#050505", background: "#000000", surface: "#070a0b", dialog: "#060809", tile: "#0c1214", border: "#203438", accent: "#00a891", accentPressed: "#007d6c", button: "#071210", buttonPressed: "#0b2621", buttonText: "#76f6df", buttonBorder: "#00a891", secondary: "#090d0e", secondaryPressed: "#10191b", text: "#ffffff", muted: "#829296", soft: "#b5c4c6", logBg: "#000000", logText: "#8dd9c8", fieldBg: "#020303", divider: "#172326", accentBorder: "#00a891", artOpacity: 0.18 },
        { id: "botanical", name: "Ботаника", swatch: "#9bd34c", background: "#101b0d", surface: "#1c2d15", dialog: "#192912", tile: "#2c411c", border: "#57793a", accent: "#9bd34c", accentPressed: "#79b330", button: "#9bd34c", buttonPressed: "#79b330", buttonText: "#142008", buttonBorder: "#c0ec78", secondary: "#263b1c", secondaryPressed: "#344e26", text: "#f4fbe8", muted: "#a6be88", soft: "#d2e3b9", logBg: "#050804", logText: "#b9d98a", fieldBg: "#101e0b", divider: "#3c5729", accentBorder: "#c0ec78", artOpacity: 0.38 },
        { id: "terracotta", name: "Терракота", swatch: "#c96f4b", background: "#211411", surface: "#35211c", dialog: "#30201b", tile: "#4b2d24", border: "#74483a", accent: "#c96f4b", accentPressed: "#a65336", button: "#c96f4b", buttonPressed: "#a65336", buttonText: "#ffffff", buttonBorder: "#dc8a67", secondary: "#472b24", secondaryPressed: "#5b352b", text: "#fff5ed", muted: "#d0a798", soft: "#e6c1b1", logBg: "#120b09", logText: "#efb59a", fieldBg: "#241613", divider: "#5d392f", accentBorder: "#dc8a67", artOpacity: 0.30 },
        { id: "indigo", name: "Индиго", swatch: "#6d6ff2", background: "#0f1024", surface: "#191b38", dialog: "#17182f", tile: "#252957", border: "#464b7c", accent: "#6366f1", accentPressed: "#4f46e5", button: "#6366f1", buttonPressed: "#4f46e5", buttonText: "#ffffff", buttonBorder: "#7f82ff", secondary: "#24264a", secondaryPressed: "#303462", text: "#f5f4ff", muted: "#a6a7cb", soft: "#c7c8e8", logBg: "#080917", logText: "#b9bcff", fieldBg: "#0f1024", divider: "#33365f", accentBorder: "#7f82ff", artOpacity: 0.24 },
        { id: "sakura", name: "Сакура", swatch: "#e978a5", background: "#21121c", surface: "#351c2c", dialog: "#301827", tile: "#4a263d", border: "#74425e", accent: "#d86491", accentPressed: "#b64b76", button: "#d86491", buttonPressed: "#b64b76", buttonText: "#ffffff", buttonBorder: "#ed8db2", secondary: "#48263a", secondaryPressed: "#5b3049", text: "#fff3f8", muted: "#d2a0b6", soft: "#ebc3d4", logBg: "#12090f", logText: "#f2a8c6", fieldBg: "#25131f", divider: "#5c3349", accentBorder: "#ed8db2", artOpacity: 0.24 },
        { id: "aurora", name: "Аврора", swatch: "#8ab5dc", background: "#151e29", surface: "#243342", dialog: "#202e3c", tile: "#31475b", border: "#59748b", accent: "#8ab5dc", accentPressed: "#6d96bc", button: "#8ab5dc", buttonPressed: "#6d96bc", buttonText: "#172a3b", buttonBorder: "#adcfe9", secondary: "#2b3e50", secondaryPressed: "#354d63", text: "#eef5fc", muted: "#a1b4c5", soft: "#c8d8e5", logBg: "#080c11", logText: "#aec8e0", fieldBg: "#162431", divider: "#405971", accentBorder: "#adcfe9", artOpacity: 0.12 },
        { id: "newyear", name: "Новогодняя", swatch: "#c83f4d", background: "#07130f", surface: "#10251d", dialog: "#0d2118", tile: "#183b2b", border: "#315c48", accent: "#c83f4d", accentPressed: "#a62e3a", button: "#b93642", buttonPressed: "#922833", buttonText: "#fff7df", buttonBorder: "#e2bd62", secondary: "#173a29", secondaryPressed: "#205038", text: "#fff7df", muted: "#c4b995", soft: "#e6ddc1", logBg: "#030907", logText: "#cbe8cf", fieldBg: "#091711", divider: "#254836", accentBorder: "#e2bd62", artOpacity: 0.34 }
    ]
    property bool newYearThemeAvailable: presence.newYearThemeAvailable
    property int currentThemeIndex: themeIndexById(presence.themeId)
    property var theme: themes[currentThemeIndex]
    property url themeArtwork: theme.id === "newyear" ? "../assets/newyear-theme.png"
        : theme.id === "botanical" ? "../assets/botanical-cannabis-theme.png" : "../assets/botanical-theme.png"
    // Each drawing has its own lowest leaf silhouette and transparent hit mask.
    property rect secretLeafBounds: theme.id === "botanical"
        ? Qt.rect(1415 * 680 / 1536, 932 * 680 / 1536, 121 * 680 / 1536, 80 * 680 / 1536)
        : Qt.rect(1462 * 680 / 1536, 934 * 680 / 1536, 40 * 680 / 1536, 61 * 680 / 1536)
    width: 390; height: 526
    minimumWidth: width; maximumWidth: width
    minimumHeight: height; maximumHeight: height
    title: "PS3 Presence"
    font.family: "Segoe UI"
    color: theme.background
    property bool settingsVisible: false
    property bool npssoVisible: false
    property bool statisticsVisible: false
    property bool aboutVisible: false
    property var storedLightOffsets: JSON.parse(presence.lightOffsets || "{}")
    property int secretLeafClicks: 0
    property bool allLightsSecretActive: false
    property bool allLightsSecretUnlocked: false
    property bool festiveAtmosphereActive: false
    property var hoveredMusicalLamp: null
    property bool musicalGarlandActive: decorationsEnabled && theme.id === "newyear" && visible
        && visibility !== Window.Minimized && !settingsVisible && !npssoVisible && !statisticsVisible && !aboutVisible
    onMusicalGarlandActiveChanged: {
        hoveredMusicalLamp = null
        presence.garlandAudio.setActive(musicalGarlandActive)
    }
    Component.onCompleted: presence.garlandAudio.setActive(musicalGarlandActive)
    Component.onDestruction: presence.garlandAudio.setActive(false)
    onThemeChanged: {
        secretLeafClicks = 0
        if (theme.id !== "newyear" && festiveAtmosphereActive) {
            festiveAtmosphereActive = false
            setAllLights(false)
        }
    }
    onClosing: function(close) { close.accepted = false; root.visible = false }

    function themeIndexById(themeId) {
        for (var i = 0; i < themes.length; ++i) {
            if (themes[i].id === themeId && (themeId !== "newyear" || newYearThemeAvailable))
                return i
        }
        for (var j = 0; j < themes.length; ++j) {
            if (themes[j].id === presence.defaultThemeId)
                return j
        }
        return 0
    }

    function selectTheme(index) {
        if (index < 0 || index >= themes.length || index === currentThemeIndex)
            return
        if (themes[index].id === "newyear" && !newYearThemeAvailable)
            return
        presence.saveTheme(themes[index].id)
    }

    function setAllLights(enabled) {
        for (var i = 0; i < lightRepeater.count; ++i) {
            var light = lightRepeater.itemAt(i)
            if (light !== null)
                light.lit = enabled
        }
    }

    function toggleFestiveAtmosphere() {
        if (theme.id !== "newyear")
            return
        festiveAtmosphereActive = !festiveAtmosphereActive
        setAllLights(festiveAtmosphereActive)
        allLightsSecretActive = false
        secretLeafClicks = 0
    }

    function lampAtPoint(px, py) {
        var nearest = null
        var distance = 14 * 14
        for (var i = 0; i < lightRepeater.count; ++i) {
            var candidate = lightRepeater.itemAt(i)
            if (candidate === null || !candidate.bulbAvailable)
                continue
            var dx = px - (candidate.x + 130)
            var dy = py - (candidate.y + 260)
            var squared = dx * dx + dy * dy
            if (squared <= distance) {
                distance = squared
                nearest = candidate
            }
        }
        return nearest
    }

    function toggleLamp(lamp) {
        lamp.lit = !lamp.lit
    }

    function updateMusicalHover(lamp) {
        if (!musicalGarlandActive)
            lamp = null
        if (hoveredMusicalLamp === lamp)
            return
        if (hoveredMusicalLamp !== null)
            presence.garlandAudio.leave(hoveredMusicalLamp.lampIndex)
        hoveredMusicalLamp = lamp
        if (lamp !== null)
            presence.garlandAudio.enter(lamp.lampIndex)
    }

    function clickSecretLeaf() {
        if (allLightsSecretUnlocked) {
            allLightsSecretActive = !allLightsSecretActive
            setAllLights(allLightsSecretActive)
            return
        }

        ++secretLeafClicks
        if (secretLeafClicks >= 3) {
            allLightsSecretUnlocked = true
            setAllLights(true)
            allLightsSecretActive = true
            secretLeafClicks = 0
        }
    }


    Rectangle {
        anchors.fill: parent
        color: "transparent"; border.color: root.theme.border
    }
    ColumnLayout {
        id: dashboard
        anchors.fill: parent; anchors.margins: 8
        spacing: 6
        RowLayout {
            objectName: "mainToolbar"
            Layout.fillWidth: true; spacing: 2
            // Fit the longer Russian labels without resizing when switching languages.
            ToolbarButton { objectName: "settingsToolbarButton"; russianText: "Настройки"; englishText: "Settings"; onClicked: presence.openSettings() }
            ToolbarButton { objectName: "openStatisticsButton"; russianText: "Статистика"; englishText: "Statistics"; onClicked: root.statisticsVisible = true }
            ToolbarButton { objectName: "openAboutButton"; russianText: "About"; englishText: "About"; onClicked: root.aboutVisible = true }
            Item { Layout.fillWidth: true }
            Button {
                id: decorationButton
                objectName: "decorationToggle"
                Layout.preferredWidth: 32; Layout.maximumWidth: 32
                implicitHeight: 26; padding: 0; hoverEnabled: true
                Accessible.name: root.decorationsEnabled ? root.tr("Выключить декор") : root.tr("Включить декор")
                onClicked: root.decorationsEnabled = !root.decorationsEnabled
                background: Rectangle {
                    radius: 3
                    color: root.decorationsEnabled || decorationButton.down ? root.theme.secondaryPressed
                        : decorationButton.hovered ? root.theme.secondary : "transparent"
                    border.width: root.decorationsEnabled || decorationButton.hovered ? 1 : 0
                    border.color: root.decorationsEnabled ? root.theme.accent : root.theme.border
                    Behavior on color { ColorAnimation { duration: 120 } }
                }
                contentItem: Item {
                    Canvas {
                        id: decorationIcon
                        anchors.centerIn: parent; width: 48; height: 48; scale: 0.5
                        property color ink: root.decorationsEnabled ? root.theme.accent : root.theme.soft
                        property color bulbColor: root.decorationsEnabled ? "#ffda79" : root.theme.muted
                        onInkChanged: requestPaint()
                        onBulbColorChanged: requestPaint()
                        onPaint: {
                            var ctx = getContext("2d")
                            ctx.reset()
                            ctx.scale(2, 2)
                            ctx.lineWidth = 1.4; ctx.lineCap = "round"; ctx.lineJoin = "round"
                            ctx.strokeStyle = ink; ctx.fillStyle = ink
                            // A curling vine and two pointed leaves.
                            ctx.beginPath(); ctx.moveTo(4, 20)
                            ctx.bezierCurveTo(9, 16, 8, 6, 18, 4); ctx.stroke()
                            ctx.beginPath(); ctx.moveTo(9, 14)
                            ctx.bezierCurveTo(3, 14, 2, 9, 3, 7)
                            ctx.bezierCurveTo(8, 7, 10, 10, 9, 14); ctx.fill()
                            ctx.beginPath(); ctx.moveTo(11, 9)
                            ctx.bezierCurveTo(11, 3, 16, 2, 19, 3)
                            ctx.bezierCurveTo(18, 7, 15, 10, 11, 9); ctx.fill()
                            // A small hanging bulb makes the lighting function explicit.
                            ctx.beginPath(); ctx.moveTo(17, 9); ctx.lineTo(17, 13); ctx.stroke()
                            ctx.fillStyle = bulbColor
                            ctx.beginPath(); ctx.arc(17, 16, 2.7, 0, Math.PI * 2); ctx.fill()
                            if (root.decorationsEnabled) {
                                ctx.strokeStyle = bulbColor; ctx.lineWidth = 1
                                ctx.beginPath()
                                ctx.moveTo(12, 16); ctx.lineTo(11, 16)
                                ctx.moveTo(22, 16); ctx.lineTo(23, 16)
                                ctx.moveTo(17, 21); ctx.lineTo(17, 22)
                                ctx.stroke()
                            }
                        }
                    }
                }
            }
        }
        Rectangle { id: toolbarDivider; objectName: "toolbarDivider"; Layout.fillWidth: true; Layout.preferredHeight: 1; color: root.theme.divider }
        Item { Layout.fillWidth: true; Layout.preferredHeight: 36 }
        Rectangle {
            objectName: "gamePanel"
            Layout.fillWidth: true; Layout.preferredHeight: 108
            color: root.theme.surface; border.color: root.theme.border; radius: 3
            RowLayout {
                anchors.fill: parent; anchors.margins: 10; spacing: 10
                Rectangle {
                    objectName: "gameCoverTile"
                    Layout.preferredWidth: 76; Layout.preferredHeight: 76
                    color: root.theme.tile; radius: 3; clip: true
                    Image {
                        id: gameCover; objectName: "currentGameCover"
                        anchors.fill: parent; anchors.margins: 4
                        source: presence.cover; asynchronous: true; cache: true
                        fillMode: Image.PreserveAspectFit
                        visible: presence.cover !== "" && status === Image.Ready
                    }
                    Image {
                        id: gamepadPlaceholder
                        objectName: "gamepadPlaceholder"
                        anchors.centerIn: parent; anchors.alignWhenCentered: false
                        width: 64; height: 64 * 156 / 254
                        source: "../assets/dualshock3.png"
                        sourceSize: Qt.size(256, 256)
                        sourceClipRect: Qt.rect(1, 54, 254, 156)
                        fillMode: Image.PreserveAspectFit
                        asynchronous: true; cache: true; smooth: true; mipmap: true
                        readonly property bool imageReady: status === Image.Ready
                        visible: presence.cover === "" || gameCover.status !== Image.Ready
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true; spacing: 4
                    Label { text: presence.hasGame ? root.tr("Сейчас играет") : root.tr("Сейчас не играет"); color: root.theme.muted; font.pixelSize: 10 }
                    Label {
                        objectName: "currentGameTitle"
                        text: presence.game; color: root.theme.text; font.pixelSize: 17; font.weight: Font.DemiBold
                        Layout.fillWidth: true; wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight
                    }
                    Label {
                        text: presence.hasGame ? presence.detail : root.tr("Ожидание игры на PlayStation 3")
                        color: root.theme.soft; font.pixelSize: 11; Layout.fillWidth: true
                        wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight
                    }
                    Label {
                        objectName: "currentGameTimer"; text: root.tr("В игре · ") + presence.sessionElapsed
                        visible: presence.hasGame; color: root.theme.accent
                        font.family: "Cascadia Mono"; font.pixelSize: 13; font.weight: Font.DemiBold
                    }
                }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true; spacing: 0
            RowLayout {
                Layout.fillWidth: true; Layout.preferredHeight: 44; spacing: 8
                Label { text: "PSN"; Layout.preferredWidth: 72; color: root.theme.muted; font.pixelSize: 11; horizontalAlignment: Text.AlignRight }
                Avatar {
                    objectName: "psnAvatar"
                    Layout.preferredWidth: 34; Layout.preferredHeight: 34
                    source: presence.avatar
                    initials: presence.psn && presence.psn !== "—" ? presence.psn.charAt(0).toUpperCase() : "?"
                    backgroundColor: root.theme.tile; textColor: root.theme.soft; borderColor: root.theme.border
                }
                Label {
                    objectName: "psnNickname"; text: presence.psn; color: root.theme.accent
                    font.pixelSize: 12; Layout.fillWidth: true; elide: Text.ElideRight
                }
            }
            DataRow { title: "Discord"; value: presence.discord }
            DataRow { title: root.tr("Платформа"); value: "PlayStation 3" }
            DataRow { objectName: "authorizationRow"; title: root.tr("Авторизация"); value: presence.auth; rowHeight: 40 }
        }
        Rectangle {
            objectName: "eventLogPanel"
            Layout.fillWidth: true; Layout.fillHeight: true
            Layout.minimumHeight: 100
            color: root.theme.logBg; border.color: root.theme.border; radius: 3
            ColumnLayout {
                anchors.fill: parent; anchors.margins: 8; spacing: 4
                Label { text: "Event Log"; color: root.theme.muted; font.pixelSize: 10 }
                ScrollView {
                    id: logScroll; Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                    TextArea {
                        id: eventLog
                        objectName: "eventLogTextArea"
                        text: presence.logs; readOnly: true; color: root.theme.logText
                        font.family: "Cascadia Mono"; font.pixelSize: 10
                        wrapMode: TextEdit.Wrap; background: null; padding: 0; selectByMouse: true
                        onTextChanged: logScroll.ScrollBar.vertical.position = 1.0
                        function copyEverything() {
                            var oldStart = selectionStart
                            var oldEnd = selectionEnd
                            selectAll()
                            copy()
                            select(oldStart, oldEnd)
                        }

                        ContextMenu.menu: Menu {
                            id: eventLogContextMenu
                            objectName: "eventLogContextMenu"
                            implicitWidth: 178
                            topPadding: 5; bottomPadding: 5
                            leftPadding: 5; rightPadding: 5

                            background: Rectangle {
                                objectName: "eventLogContextMenuBackground"
                                property color outlineColor: root.theme.border
                                color: root.theme.dialog
                                border.width: 1
                                border.color: outlineColor
                                radius: 10
                            }

                            EventLogMenuItem {
                                objectName: "eventLogCopySelection"
                                text: root.tr("Копировать")
                                enabled: eventLog.selectedText.length > 0
                                onTriggered: eventLog.copy()
                            }
                            EventLogMenuItem {
                                objectName: "eventLogCopyAll"
                                text: root.tr("Копировать весь лог")
                                enabled: eventLog.text.length > 0
                                onTriggered: eventLog.copyEverything()
                            }
                            EventLogMenuItem {
                                objectName: "eventLogSelectAll"
                                text: root.tr("Выделить всё")
                                enabled: eventLog.text.length > 0
                                onTriggered: eventLog.selectAll()
                            }
                        }
                    }
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 4
            Label { text: root.tr(root.theme.name); color: root.theme.muted; font.pixelSize: 10; Layout.fillWidth: true }
            Repeater {
                model: root.themes
                delegate: Item {
                    readonly property bool seasonallyAvailable: modelData.id !== "newyear" || root.newYearThemeAvailable
                    width: seasonallyAvailable ? 18 : 0; height: 20
                    visible: seasonallyAvailable
                    readonly property bool selected: index === root.currentThemeIndex
                    Rectangle {
                        anchors.centerIn: parent; width: parent.selected ? 15 : 12; height: width; radius: width / 2
                        color: modelData.swatch; border.width: parent.selected ? 2 : 1
                        border.color: parent.selected ? root.theme.text : root.theme.muted
                        scale: themeMouse.pressed ? 0.85 : (themeMouse.containsMouse ? 1.12 : 1.0)
                        Behavior on scale { NumberAnimation { duration: 120 } }
                    }
                    MouseArea {
                        id: themeMouse; objectName: "themeHitTarget" + index
                        readonly property bool tooltipShown: ToolTip.toolTip.visible && ToolTip.toolTip.text === root.tr(modelData.name)
                        anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: root.selectTheme(index)
                        ToolTip.visible: containsMouse; ToolTip.text: root.tr(modelData.name); ToolTip.delay: 350
                    }
                }
            }
        }
        Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: root.theme.divider }
        RowLayout {
            Layout.fillWidth: true; spacing: 8
            AppButton {
                objectName: "reconnectDiscordButton"; text: root.tr("Переподключить Discord")
                Layout.minimumWidth: 175; Layout.preferredWidth: 175; Layout.maximumWidth: 175
                onClicked: presence.reconnect()
            }
            Item { Layout.fillWidth: true }
            Label {
                id: presenceStatusLabel
                objectName: "presenceStatus"; text: presence.phase; color: root.theme.soft; font.pixelSize: 10
                Layout.maximumWidth: 140; elide: Text.ElideRight; horizontalAlignment: Text.AlignRight
            }
            FontMetrics { id: statusFontMetrics; font: presenceStatusLabel.font }
            ConnectionIndicator {
                id: statusIndicator
                objectName: "presenceStatusIndicator"
                Layout.minimumWidth: 18; Layout.preferredWidth: 18; Layout.maximumWidth: 18
                Layout.preferredHeight: 18; Layout.alignment: Qt.AlignVCenter
                color: presence.color; mode: presence.psnConnectionState
                active: root.visible && root.visibility !== Window.Minimized
                // Center on visible letters, not the line box's descender space.
                transform: Translate {
                    y: Math.round(presenceStatusLabel.y + presenceStatusLabel.baselineOffset
                        - statusFontMetrics.capitalHeight / 2 - statusIndicator.y - statusIndicator.height / 2)
                }
            }
        }
    }
        RowLayout {
            objectName: "brandHeader"
            x: 8; y: 47; width: root.width - 16; height: 36; spacing: 8; z: 12
            Item {
                Layout.preferredWidth: 48; Layout.minimumWidth: 48; Layout.maximumWidth: 48
                Layout.fillHeight: true
                Image {
                    objectName: "programLogo"
                    anchors.centerIn: parent
                    width: 32; height: 32
                    source: "../assets/presence-mark.svg"; sourceSize: Qt.size(128, 128)
                    fillMode: Image.PreserveAspectFit; smooth: true; mipmap: true
                }
            }
            ColumnLayout {
                Layout.fillWidth: true; spacing: 1
                Label { objectName: "programHeading"; Layout.fillWidth: true; text: "PS3 PRESENCE"; color: root.theme.text; font.pixelSize: 16; font.weight: Font.DemiBold; font.letterSpacing: 0.5 }
                Label { Layout.fillWidth: true; text: "PSN → Discord Rich Presence"; color: root.theme.muted; font.pixelSize: 10 }
            }
            Item { Layout.preferredWidth: 96; Layout.minimumWidth: 96; Layout.maximumWidth: 96 }
        }
    RowLayout {
        id: languageSwitcher
        objectName: "languageSwitcher"
        x: root.width - width - 8; y: 47 + (36 - height) / 2; z: 12
        spacing: 2
        LanguageButton { objectName: "ruLanguageButton"; code: "ru"; text: "RU" }
        Label { text: "|"; color: root.theme.muted; font.pixelSize: 11 }
        LanguageButton { objectName: "enLanguageButton"; code: "en"; text: "EN" }
    }
    Image {
        objectName: "decorationArtwork"
        y: root.artTop
        width: 680; height: 780
        scale: root.artScale; transformOrigin: Item.TopLeft; z: 4
        visible: root.decorationsEnabled
        source: root.decorationsEnabled ? root.themeArtwork : ""
        fillMode: Image.PreserveAspectFit
        horizontalAlignment: Image.AlignHCenter; verticalAlignment: Image.AlignTop
        asynchronous: true; smooth: true
    }
    // Soft diffuse halos; the transparent hit targets sit above every artwork layer.
    Item {
        objectName: "garlandLayer"
        width: 680; height: 780
        y: root.artTop; visible: root.decorationsEnabled; enabled: root.decorationsEnabled
        scale: root.artScale; transformOrigin: Item.TopLeft; z: 13
        Repeater {
            id: lightRepeater
            model: [
                { px: 80,  py: 19 }, { px: 120, py: 35 }, { px: 149, py: 54 },
                { px: 201, py: 42 }, { px: 256, py: 14 }, { px: 386, py: 30 },
                { px: 473, py: 35 }, { px: 551, py: 20 }, { px: 545, py: 32 },
                { px: 587, py: 26 }, { px: 569, py: 53 }, { px: 615, py: 40 },
                { px: 586, py: 73 }, { px: 634, py: 73 }, { px: 667, py: 106 },
                { px: 48, py: 115 },
                { px: 38, py: 180 }, { px: 644, py: 168 },
                // Extra low-left bulb exists only in the new cannabis drawing.
                { px: 48, py: 252, botanicalOnly: true }
            ]
            delegate: Item {
                id: lamp
                objectName: "garlandLamp" + index
                property int lampIndex: index
                property bool bulbAvailable: modelData.botanicalOnly === true
                    ? root.theme.id === "botanical"
                    : root.theme.id !== "newyear" || (index !== 8 && index !== 12)
                property bool lit: false
                property real glowLevel: 0.0
                property int glowOffsetX: 0
                property int glowOffsetY: 0
                // Extra room above every bulb lets the halo fade to fully
                // transparent before it reaches the window edge.
                x: modelData.px - 130; y: modelData.py - 260
                width: 260; height: 620

                Component.onCompleted: {
                    var saved = root.storedLightOffsets[String(lampIndex)]
                    if (saved && saved.length === 2) {
                        glowOffsetX = saved[0]
                        glowOffsetY = saved[1]
                    }
                }
                onGlowOffsetXChanged: lampGlow.requestPaint()
                onGlowOffsetYChanged: lampGlow.requestPaint()
                onLitChanged: {
                    // Every switch interrupts the old transition immediately.
                    // A visible initial attack avoids a perceived cooldown when
                    // all bulbs are relit before their previous fade finishes.
                    glowAnimation.stop()
                    if (lit)
                        glowLevel = Math.max(glowLevel, 0.30)
                    glowAnimation.from = glowLevel
                    glowAnimation.to = lit ? 1.0 : 0.0
                    glowAnimation.duration = lit ? 200 : 160
                    glowAnimation.start()
                }

                NumberAnimation {
                    id: glowAnimation
                    target: lamp; property: "glowLevel"
                    easing.type: Easing.OutCubic
                }

                Canvas {
                    id: lampGlow
                    property bool painted: false
                    anchors.fill: parent
                    opacity: lamp.bulbAvailable ? lamp.glowLevel : 0
                    onOpacityChanged: { if (opacity > 0 && !painted) requestPaint() }
                    onPaint: {
                        var ctx = getContext("2d")
                        ctx.clearRect(0, 0, width, height)
                        ctx.save()
                        ctx.translate(lamp.glowOffsetX, lamp.glowOffsetY)

                        // The glow originates at the bulb itself. A soft mask
                        // fades its upper half, leaving a natural downward falloff.
                        var halo = ctx.createRadialGradient(130, 247, 4, 130, 247, 100)
                        halo.addColorStop(0.0, "rgba(255, 239, 185, 0.42)")
                        halo.addColorStop(0.22, "rgba(255, 213, 125, 0.28)")
                        halo.addColorStop(0.58, "rgba(255, 181, 75, 0.12)")
                        halo.addColorStop(1.0, "rgba(255, 158, 45, 0.00)")
                        ctx.fillStyle = halo
                        ctx.fillRect(0, 132, width, 260)

                        ctx.globalCompositeOperation = "destination-in"
                        var downwardMask = ctx.createLinearGradient(0, 192, 0, 282)
                        downwardMask.addColorStop(0.0, "rgba(255, 255, 255, 0.00)")
                        downwardMask.addColorStop(0.58, "rgba(255, 255, 255, 0.72)")
                        downwardMask.addColorStop(1.0, "rgba(255, 255, 255, 1.00)")
                        ctx.fillStyle = downwardMask
                        ctx.fillRect(0, 132, width, 300)
                        ctx.globalCompositeOperation = "source-over"
                        ctx.restore()
                        painted = true
                    }
                }
                MouseArea {
                    objectName: "garlandHitTarget" + index
                    x: 116; y: 246; width: 28; height: 28
                    enabled: lamp.bulbAvailable
                    visible: lamp.bulbAvailable
                    hoverEnabled: root.musicalGarlandActive
                    cursorShape: Qt.PointingHandCursor
                    onEntered: root.updateMusicalHover(root.lampAtPoint(lamp.x + x + mouseX, lamp.y + y + mouseY))
                    onPositionChanged: root.updateMusicalHover(root.lampAtPoint(lamp.x + x + mouseX, lamp.y + y + mouseY))
                    onExited: { if (root.hoveredMusicalLamp === lamp) root.updateMusicalHover(null) }
                    onPressed: function(mouse) {
                        // Overlapping targets pass the press to the closest bulb.
                        mouse.accepted = root.lampAtPoint(lamp.x + x + mouse.x, lamp.y + y + mouse.y) === lamp
                        // Leave the language buttons clickable under decoration:
                        // only the actual bulb centre takes priority over them.
                        var point = mapToItem(languageSwitcher, mouse.x, mouse.y)
                        if (point.x >= 0 && point.x < languageSwitcher.width && point.y >= 0 && point.y < languageSwitcher.height) {
                            var dx = (mouse.x - width/2) * root.artScale
                            var dy = (mouse.y - height/2) * root.artScale
                            if (dx*dx + dy*dy > 9) mouse.accepted = false
                        }
                    }
                    onClicked: root.toggleLamp(lamp)
                }
            }
        }
    }
    // Three presses unlock the Easter egg once. Afterwards every press toggles
    // the whole garland immediately, even while the previous fade is running.
    Item {
        objectName: "decorationTargets"
        width: 680; height: 780
        y: root.artTop; visible: root.decorationsEnabled; enabled: root.decorationsEnabled
        scale: root.artScale; transformOrigin: Item.TopLeft; z: 14
        Loader {
            id: leafTarget
            x: root.secretLeafBounds.x; y: root.secretLeafBounds.y
            width: root.secretLeafBounds.width; height: root.secretLeafBounds.height
            // Unmount the inactive theme's target: enabled=false alone still
            // leaves its cursor shape active in Qt Quick.
            active: root.decorationsEnabled && root.theme.id !== "newyear"
            sourceComponent: MouseArea {
                objectName: "secretLeafClick"
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                containmentMask: QtObject {
                    function contains(point: point): bool {
                        return presence.isSecretLeafHit(leafTarget.x + point.x, leafTarget.y + point.y)
                    }
                }
                // Count presses, including native double-click sequences.
                onPressed: function(mouse) {
                    // Recheck fractional press coordinates: containment tests
                    // use integer points and can round onto an opaque pixel.
                    mouse.accepted = presence.isSecretLeafHit(leafTarget.x + mouse.x, leafTarget.y + mouse.y)
                    if (mouse.accepted) root.clickSecretLeaf()
                }
            }
        }
        Loader {
            x: 648; y: 306; width: 32; height: 42
            active: root.decorationsEnabled && root.theme.id === "newyear"
            sourceComponent: MouseArea {
                objectName: "festivePineconeClick"
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: root.toggleFestiveAtmosphere()
            }
        }
    }
    Snowfall {
        objectName: "festiveSnowfall"
        width: 680; height: 916; scale: root.artScale; transformOrigin: Item.TopLeft
        z: 15
        active: root.decorationsEnabled && root.theme.id === "newyear" && root.festiveAtmosphereActive
        visible: root.decorationsEnabled && intensity > 0.001
        renderingEnabled: root.decorationsEnabled && root.visible && root.visibility !== Window.Minimized
    }
    LeafFall {
        objectName: "botanicalLeafFall"
        width: 680; height: 916; scale: root.artScale; transformOrigin: Item.TopLeft
        z: 15
        active: root.decorationsEnabled && root.theme.id === "botanical" && root.allLightsSecretActive
        visible: root.decorationsEnabled && root.theme.id === "botanical" && intensity > 0.001
        renderingEnabled: root.decorationsEnabled && root.visible && root.visibility !== Window.Minimized
            && !root.settingsVisible && !root.npssoVisible && !root.statisticsVisible && !root.aboutVisible && root.theme.id === "botanical"
    }
    GameStatisticsDialog {
        objectName: "gameStatisticsDialog"
        parent: Overlay.overlay
        visible: root.statisticsVisible
        uiScale: root.uiScale; colors: root.theme
        translator: presence
        statisticsModel: presence.gameStatistics
        historyModel: presence.sessionHistory
        accountName: presence.statisticsAccount
        totalPlaytime: presence.totalPlaytime
        collectionStartedDate: presence.statisticsSince
        statusMessage: presence.statisticsError
        onOpened: presence.refreshStatistics()
        onClosed: root.statisticsVisible = false
    }
    Dialog {
        id: aboutDialog
        objectName: "aboutDialog"
        property bool usernameCopied: false
        property bool profileOpenFailed: false
        property bool webOpenFailed: false
        parent: Overlay.overlay
        modal: true; visible: root.aboutVisible
        x: (parent.width - width) / 2
        y: (parent.height - height) / 2
        width: root.width - 24; padding: 16
        onClosed: {
            root.aboutVisible = false
            usernameCopied = false
            profileOpenFailed = false
            webOpenFailed = false
            discordCopyTimer.stop()
        }
        Timer { id: discordCopyTimer; interval: 1800; onTriggered: aboutDialog.usernameCopied = false }
        background: Rectangle { color: root.theme.dialog; radius: 4; border.color: root.theme.border }
        contentItem: Item {
            implicitHeight: 240
            Label { objectName: "programVersion"; text: "v. " + presence.version; color: root.theme.muted; font.pixelSize: 11 }
            ColumnLayout {
                y: 34; width: parent.width; spacing: 8
                RowLayout {
                    Layout.fillWidth: true; spacing: 8
                    Item {
                        id: discordLogo
                        objectName: "authorDiscordLogo"
                        Layout.minimumWidth: 16; Layout.preferredWidth: 16; Layout.maximumWidth: 16
                        Layout.preferredHeight: 16
                        Layout.alignment: Qt.AlignVCenter
                        Layout.rightMargin: -2
                        transform: Translate { y: 1 }
                        property url source: root.theme.id === "light" ? "../assets/discord-mark-black.svg" : "../assets/discord-mark-white.svg"
                        readonly property bool imageReady: discordLogoFace.status === Image.Ready
                        Accessible.name: "Discord"
                        // A restrained two-step shadow adds depth without effects,
                        // shader dependencies or changing the logo silhouette.
                        Image {
                            objectName: "authorDiscordLogoSoftShadow"
                            width: 16; height: 12; y: 4
                            source: "../assets/discord-mark-black.svg"
                            sourceSize: Qt.size(160, 120)
                            fillMode: Image.PreserveAspectFit; smooth: true; mipmap: true
                            opacity: root.theme.id === "light" ? 0.06 : 0.14
                        }
                        Image {
                            objectName: "authorDiscordLogoShadow"
                            width: 16; height: 12; y: 3
                            source: "../assets/discord-mark-black.svg"
                            sourceSize: Qt.size(160, 120)
                            fillMode: Image.PreserveAspectFit; smooth: true; mipmap: true
                            opacity: root.theme.id === "light" ? 0.14 : 0.3
                        }
                        Image {
                            id: discordLogoFace
                            objectName: "authorDiscordLogoFace"
                            width: 16; height: 12; y: 2
                            source: discordLogo.source
                            sourceSize: Qt.size(160, 120)
                            fillMode: Image.PreserveAspectFit; smooth: true; mipmap: true
                            opacity: root.theme.id === "light" ? 0.9 : 0.92
                        }
                    }
                    AboutLink {
                        id: authorDiscordLink
                        objectName: "authorDiscordUsername"
                        text: presence.authorDiscordUsername
                        onClicked: {
                            presence.copyAuthorDiscordUsername()
                            aboutDialog.usernameCopied = true
                            discordCopyTimer.restart()
                            aboutDialog.profileOpenFailed = !presence.openAuthorDiscord()
                        }
                    }
                    FallingPhrase {
                        objectName: "aboutSunPraise"
                        text: "Praise Teh Sun \\[T]/"
                        color: root.theme.muted
                        active: aboutDialog.visible && root.visible && root.visibility !== Window.Minimized
                    }
                    Item { Layout.fillWidth: true }
                }
                Label {
                    objectName: "authorDiscordFeedback"
                    visible: aboutDialog.profileOpenFailed || aboutDialog.usernameCopied
                    text: aboutDialog.profileOpenFailed
                        ? root.tr("Не удалось открыть профиль. Ник скопирован — найди автора в Discord.")
                        : root.tr("Ник скопирован")
                    color: root.theme.muted; font.pixelSize: 10
                    Layout.fillWidth: true; wrapMode: Text.WordWrap
                }
                RowLayout {
                    Layout.fillWidth: true; spacing: 6
                    Image {
                        objectName: "aboutGitHubLogo"
                        readonly property bool imageReady: status === Image.Ready
                        Layout.minimumWidth: 16; Layout.preferredWidth: 16; Layout.maximumWidth: 16
                        Layout.preferredHeight: 16; Layout.alignment: Qt.AlignVCenter
                        source: root.theme.id === "light" ? "../assets/github-mark-black.svg" : "../assets/github-mark-white.svg"
                        sourceSize: Qt.size(160, 160)
                        fillMode: Image.PreserveAspectFit; smooth: true; mipmap: true
                        opacity: root.theme.id === "light" ? 0.9 : 0.92
                        Accessible.name: "GitHub"
                    }
                    AboutLink {
                        objectName: "aboutGitHubRepository"
                        text: "PS3Presence"
                        Accessible.name: "PS3Presence — GitHub"
                        onClicked: aboutDialog.webOpenFailed = !presence.openGitHubRepository()
                    }
                    Item { Layout.fillWidth: true }
                }
                Label {
                    objectName: "aboutWebLinkFeedback"
                    visible: aboutDialog.webOpenFailed
                    text: root.tr("Не удалось открыть ссылку в браузере.")
                    color: root.theme.muted; font.pixelSize: 10
                    Layout.fillWidth: true; wrapMode: Text.WordWrap
                }
            }
            AboutLink {
                objectName: "aboutGitHubIssues"
                anchors.left: parent.left
                anchors.bottom: aboutAnimation.top
                anchors.bottomMargin: 8
                implicitHeight: 20
                font.pixelSize: 10; font.weight: Font.Normal
                text: root.tr("Сообщить о проблеме")
                onClicked: aboutDialog.webOpenFailed = !presence.openGitHubIssues()
            }
            TransparentGif {
                id: aboutAnimation
                objectName: "aboutAnimation"
                anchors.left: parent.left; anchors.bottom: parent.bottom
                width: parent.width / 2; height: width * 96 / 636
                sourceClipRect: Qt.rect(0, 130, 636, 96)
                roundedCapRect: Qt.rect(240, 148, 68, 20)
                source: aboutDialog.visible ? Qt.resolvedUrl("../assets/about-pacman.gif") : ""
                playing: aboutDialog.visible && root.visible && root.visibility !== Window.Minimized
            }
            AppButton { objectName: "closeAboutButton"; anchors.right: parent.right; anchors.bottom: parent.bottom; text: root.tr("Закрыть"); onClicked: aboutDialog.close() }
        }
    }
    Dialog {
        id: settingsDialog
        objectName: "settingsDialog"
        parent: Overlay.overlay
        modal: true; visible: root.settingsVisible
        scale: root.uiScale
        transformOrigin: Popup.TopLeft
        x: (parent.width - width * scale) / 2
        y: (parent.height - height * scale) / 2
        width: root.width - 24; padding: 16
        onOpened: {
            clientId.text = presence.settingsClientId
            interval.text = String(presence.settingsInterval)
            imageKey.text = presence.settingsImage
            autostart.checked = presence.settingsAutostart
        }
        onClosed: root.settingsVisible = false
        background: Rectangle { color: root.theme.dialog; radius: 4; border.color: root.theme.border }
        contentItem: ColumnLayout { spacing: 8
            Label { text: root.tr("Настройки"); color: root.theme.text; font.pixelSize: 18; font.weight: Font.DemiBold }
            Label { text: root.tr("Подключение, опрос и автозапуск"); color: root.theme.muted; font.pixelSize: 11 }
            Label { text: "Discord Application ID"; color: root.theme.text; font.pixelSize: 11; topPadding: 6 }
            TextField { id: clientId; objectName: "settingsClientIdField"; Layout.fillWidth: true; Layout.preferredHeight: 28; color: root.theme.text; font.pixelSize: 11; selectByMouse: true
                background: Rectangle { radius: 3; color: root.theme.fieldBg; border.color: clientId.activeFocus ? root.theme.accentBorder : root.theme.border }
            }
            Label { text: root.tr("Интервал опроса, секунд"); color: root.theme.text; font.pixelSize: 11 }
            TextField { id: interval; objectName: "settingsIntervalField"; inputMethodHints: Qt.ImhDigitsOnly; selectByMouse: true; Layout.fillWidth: true; Layout.preferredHeight: 28; color: root.theme.text; font.pixelSize: 11
                validator: IntValidator { bottom: 15; top: 2147483647 }
                background: Rectangle { radius: 3; color: root.theme.fieldBg; border.color: interval.activeFocus ? root.theme.accentBorder : root.theme.border }
            }
            Label { text: root.tr("Не менее 15 секунд"); color: root.theme.muted; font.pixelSize: 11 }
            Label { text: root.tr("Fallback-обложка"); color: root.theme.text; font.pixelSize: 11 }
            TextField { id: imageKey; objectName: "settingsImageField"; placeholderText: root.tr("Необязательный ключ изображения"); placeholderTextColor: root.theme.muted; Layout.fillWidth: true; Layout.preferredHeight: 28; color: root.theme.text; font.pixelSize: 11
                background: Rectangle { radius: 3; color: root.theme.fieldBg; border.color: imageKey.activeFocus ? root.theme.accentBorder : root.theme.border }
            }
            CheckBox { id: autostart; objectName: "settingsAutostartCheckBox"; text: root.tr("Запускать вместе с Windows"); implicitHeight: 26; font.pixelSize: 11
                contentItem: Label { text: autostart.text; color: root.theme.text; font.pixelSize: 11; verticalAlignment: Text.AlignVCenter; leftPadding: autostart.indicator.width + 10 }
                indicator: Rectangle { implicitWidth: 18; implicitHeight: 18; x: autostart.leftPadding; y: parent.height / 2 - height / 2; radius: 5; color: autostart.checked ? root.theme.accent : root.theme.fieldBg; border.color: autostart.checked ? root.theme.accentBorder : root.theme.border
                    Label { anchors.centerIn: parent; visible: autostart.checked; text: "✓"; color: root.theme.id === "botanical" || root.theme.id === "aurora" ? root.theme.buttonText : "white"; font.pixelSize: 11; font.weight: Font.Bold }
                }
            }
            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: root.theme.divider; Layout.topMargin: 4; Layout.bottomMargin: 2 }
            RowLayout { Layout.fillWidth: true
                ColumnLayout { Layout.fillWidth: true
                    Label { text: "NPSSO"; color: root.theme.text; font.pixelSize: 11; font.weight: Font.DemiBold }
                    Label { text: presence.npssoMessage; color: root.theme.muted; font.pixelSize: 10; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                }
                AppButton { text: root.tr("Обновить NPSSO"); onClicked: root.npssoVisible = true }
            }
            Label { objectName: "settingsErrorLabel"; text: presence.settingsError; visible: text.length > 0; color: "#df8f79"; font.pixelSize: 10; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            RowLayout { Layout.fillWidth: true; Item { Layout.fillWidth: true }
                AppButton { text: root.tr("Отмена"); secondary: true; onClicked: settingsDialog.close() }
                AppButton { objectName: "saveSettingsButton"; text: root.tr("Сохранить"); onClicked: {
                    if (presence.saveSettings(clientId.text, interval.acceptableInput ? Number(interval.text) : 0, imageKey.text, autostart.checked))
                        settingsDialog.close()
                } }
            }
        }
    }
    Dialog {
        id: npssoDialog
        objectName: "npssoDialog"
        parent: Overlay.overlay
        modal: true; visible: root.npssoVisible
        scale: root.uiScale
        transformOrigin: Popup.TopLeft
        x: (parent.width - width * scale) / 2
        y: (parent.height - height * scale) / 2
        width: root.width - 24; padding: 16
        onAboutToShow: presence.beginNpssoEdit()
        onClosed: {
            presence.cancelNpssoEdit()
            root.npssoVisible = false
        }
        background: Rectangle { color: root.theme.dialog; radius: 4; border.color: root.theme.border }
        contentItem: ColumnLayout { spacing: 10
            Label { text: root.tr("Обновление NPSSO"); color: root.theme.text; font.pixelSize: 18; font.weight: Font.DemiBold }
            Label { text: root.tr("1. Войди в PSN в обычном браузере.\n2. Открой ssocookie в той же вкладке.\n3. Скопируй весь JSON-ответ.\n4. Вернись сюда и вставь его из буфера."); color: root.theme.soft; wrapMode: Text.WordWrap; lineHeight: 1.35; Layout.fillWidth: true }
            AppButton { text: root.tr("Открыть вход Sony"); Layout.fillWidth: true; onClicked: presence.openSonyLogin() }
            AppButton { text: root.tr("Открыть страницу ssocookie"); Layout.fillWidth: true; onClicked: presence.openSsoCookie() }
            AppButton { objectName: "pasteNpssoButton"; text: root.tr("Вставить из буфера"); Layout.fillWidth: true; onClicked: presence.pasteNpsso() }
            Label { text: presence.npssoMessage; color: root.theme.muted; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            RowLayout { Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                AppButton { objectName: "cancelNpssoButton"; text: root.tr("Отмена"); secondary: true; onClicked: {
                    presence.cancelNpssoEdit()
                    npssoDialog.close()
                } }
                AppButton { objectName: "confirmNpssoButton"; text: root.tr("Готово"); secondary: true; onClicked: {
                    presence.confirmNpssoEdit()
                    npssoDialog.close()
                } }
            }
        }
    }
    component DataRow: Item {
        property string title
        property string value
        property real rowHeight: 26
        Layout.fillWidth: true; Layout.preferredHeight: rowHeight
        Rectangle { width: parent.width; height: 1; color: root.theme.divider }
        RowLayout {
            anchors.fill: parent; spacing: 8
            Label { text: parent.parent.title; Layout.preferredWidth: 72; color: root.theme.muted; font.pixelSize: 11; horizontalAlignment: Text.AlignRight }
            Label {
                text: parent.parent.value; color: root.theme.accent; font.pixelSize: 11
                Layout.fillWidth: true; wrapMode: Text.WordWrap
            }
        }
    }
    component AboutLink: Button {
        id: link
        implicitWidth: linkText.implicitWidth; implicitHeight: 26
        font.pixelSize: 14; font.weight: Font.DemiBold
        padding: 0; hoverEnabled: true
        background: Item {}
        contentItem: Label {
            id: linkText
            text: link.text; color: root.theme.accent
            font.pixelSize: link.font.pixelSize
            font.weight: link.font.weight; font.underline: true
            verticalAlignment: Text.AlignVCenter
            opacity: link.down ? 0.65 : 1
        }
        HoverHandler { cursorShape: Qt.PointingHandCursor }
    }
    component LanguageButton: Button {
        id: languageButton
        property string code
        readonly property bool selected: presence.language === code
        implicitWidth: 44; implicitHeight: 24
        padding: 3; hoverEnabled: true
        Accessible.name: code === "ru" ? "Русский" : "English"
        onClicked: presence.saveLanguage(code)
        background: Rectangle {
            radius: 3
            color: languageButton.selected || languageButton.down ? root.theme.secondaryPressed : languageButton.hovered ? root.theme.secondary : "transparent"
            border.width: languageButton.selected ? 1 : 0
            border.color: root.theme.accent
        }
        contentItem: RowLayout {
            spacing: 3
            Canvas {
                Layout.preferredWidth: 16; Layout.preferredHeight: 10
                onPaint: {
                    var ctx = getContext("2d")
                    ctx.reset()
                    if (languageButton.code === "ru") {
                        ctx.fillStyle = "#ffffff"; ctx.fillRect(0, 0, 16, 10/3)
                        ctx.fillStyle = "#245ac0"; ctx.fillRect(0, 10/3, 16, 10/3)
                        ctx.fillStyle = "#d43840"; ctx.fillRect(0, 20/3, 16, 10/3)
                    } else {
                        ctx.fillStyle = "#163572"; ctx.fillRect(0, 0, 16, 10)
                        ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 2.6
                        ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(16, 10); ctx.moveTo(16, 0); ctx.lineTo(0, 10); ctx.stroke()
                        ctx.strokeStyle = "#d43840"; ctx.lineWidth = 1
                        ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(16, 10); ctx.moveTo(16, 0); ctx.lineTo(0, 10); ctx.stroke()
                        ctx.fillStyle = "#ffffff"; ctx.fillRect(6, 0, 4, 10); ctx.fillRect(0, 3, 16, 4)
                        ctx.fillStyle = "#d43840"; ctx.fillRect(7, 0, 2, 10); ctx.fillRect(0, 4, 16, 2)
                    }
                }
            }
            Label { text: languageButton.text; color: languageButton.selected ? root.theme.accent : root.theme.muted; font.pixelSize: 10; Layout.fillWidth: true }
        }
    }
    component ToolbarButton: AppButton {
        id: toolbarButton
        property string russianText
        property string englishText
        text: root.tr(russianText)
        implicitWidth: Math.ceil(Math.max(russianTextSize.advanceWidth, englishTextSize.advanceWidth)) + leftPadding + rightPadding
        Layout.minimumWidth: implicitWidth
        Layout.preferredWidth: implicitWidth
        Layout.maximumWidth: implicitWidth
        leftPadding: 4; rightPadding: 4
        flat: true
        TextMetrics { id: russianTextSize; text: toolbarButton.russianText; font: toolbarButton.contentItem.font }
        TextMetrics { id: englishTextSize; text: toolbarButton.englishText; font: toolbarButton.contentItem.font }
    }
    component AppButton: Button {
        id: button
        property bool secondary: true
        property bool selected: false
        property string toolTip: ""
        implicitWidth: Math.max(64, label.implicitWidth + 16)
        implicitHeight: 26
        Layout.minimumWidth: 0
        leftPadding: 8; rightPadding: 8; topPadding: 0; bottomPadding: 0
        hoverEnabled: true
        contentItem: Label {
            id: label; text: button.text
            color: root.theme.text; font.pixelSize: 11
            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
        background: Rectangle {
            radius: 2
            color: button.down || button.selected ? root.theme.secondaryPressed
                : button.hovered ? root.theme.secondary : button.flat ? "transparent" : root.theme.fieldBg
            border.width: button.flat && !button.selected && !button.hovered ? 0 : 1
            border.color: button.selected ? root.theme.accent : root.theme.border
            Behavior on color { ColorAnimation { duration: 100 } }
        }
        ToolTip.visible: hovered && toolTip.length > 0
        ToolTip.text: toolTip; ToolTip.delay: 400
    }
    component EventLogMenuItem: MenuItem {
        id: menuItem
        implicitWidth: 168
        implicitHeight: 30
        leftPadding: 11; rightPadding: 11
        topPadding: 0; bottomPadding: 0

        contentItem: Text {
            text: menuItem.text
            color: menuItem.enabled ? root.theme.text : root.theme.muted
            opacity: menuItem.enabled ? 1.0 : 0.48
            font.pixelSize: 12
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
        background: Rectangle {
            radius: 6
            color: menuItem.highlighted
                ? root.theme.secondaryPressed
                : (menuItem.down ? root.theme.secondary : "transparent")
        }
    }
}
