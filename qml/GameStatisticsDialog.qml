import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: statistics
    property var translator
    function tr(text) { return translator.language === "en" ? translator.translate(text) : text }
    property var colors
    property var statisticsModel
    property var historyModel
    property bool historyMode: false
    readonly property int gameCardHeight: 88
    readonly property int sessionCardHeight: 132
    readonly property int tabHeight: 26
    property real uiScale: 1.0
    property string accountName: "—"
    property string totalPlaytime: "00:00:00"
    property string collectionStartedDate: ""
    property string statusMessage: ""
    readonly property var activeList: historyMode ? historyList : gameList
    readonly property color edgeColor: colors.dialog
    modal: true
    width: (parent.width - 24) / uiScale; height: (parent.height - 24) / uiScale; padding: 12
    scale: uiScale; transformOrigin: Popup.TopLeft
    x: (parent.width - width * scale) / 2
    y: (parent.height - height * scale) / 2
    background: Rectangle { color: statistics.colors.dialog; radius: 4; border.color: statistics.colors.border }
    contentItem: ColumnLayout {
        spacing: 8
        Label { text: statistics.tr("Статистика игр"); color: statistics.colors.text; font.pixelSize: 18; font.weight: Font.DemiBold }
        Label { text: "PSN · " + statistics.accountName; color: statistics.colors.muted; font.pixelSize: 11 }
        Rectangle {
            Layout.fillWidth: true; Layout.preferredHeight: 60
            radius: 3; color: statistics.colors.surface; border.color: statistics.colors.border
            ColumnLayout {
                anchors.fill: parent; anchors.margins: 8; spacing: 2
                RowLayout {
                    Layout.fillWidth: true
                    Label { text: statistics.tr("Общее время"); color: statistics.colors.muted; font.pixelSize: 11 }
                    Label { objectName: "statisticsTotal"; text: statistics.totalPlaytime; color: statistics.colors.accent; font.family: "Cascadia Mono"; font.pixelSize: 18; font.weight: Font.DemiBold }
                    Item { Layout.fillWidth: true }
                    Label { text: statistics.tr("Игр: ") + gameList.count; color: statistics.colors.soft; font.pixelSize: 11 }
                }
                Label {
                    objectName: "statisticsSince"
                    text: statistics.collectionStartedDate ? statistics.tr("Статистика с ") + statistics.collectionStartedDate : statistics.tr("Подсчёт начнётся с первого обнаружения игры")
                    color: statistics.colors.muted; font.pixelSize: 11
                    Layout.fillWidth: true; elide: Text.ElideRight
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 8
            Button {
                id: gamesTab; objectName: "statisticsGamesTab"
                text: statistics.tr("Игры"); Layout.fillWidth: true; Layout.preferredWidth: 1; implicitHeight: statistics.tabHeight
                onClicked: statistics.historyMode = false
                background: Rectangle { radius: 3; color: !statistics.historyMode ? statistics.colors.secondary : statistics.colors.surface; border.color: !statistics.historyMode ? statistics.colors.accentBorder : statistics.colors.border }
                contentItem: Label { text: gamesTab.text; color: statistics.colors.text; font.pixelSize: 11; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
            }
            Button {
                id: sessionsTab; objectName: "statisticsSessionsTab"
                text: statistics.tr("Сессии"); Layout.fillWidth: true; Layout.preferredWidth: 1; implicitHeight: statistics.tabHeight
                onClicked: statistics.historyMode = true
                background: Rectangle { radius: 3; color: statistics.historyMode ? statistics.colors.secondary : statistics.colors.surface; border.color: statistics.historyMode ? statistics.colors.accentBorder : statistics.colors.border }
                contentItem: Label { text: sessionsTab.text; color: statistics.colors.text; font.pixelSize: 11; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
            }
        }
        Item {
            objectName: "statisticsViewport"
            Layout.fillWidth: true; Layout.fillHeight: true
            Label {
                anchors.centerIn: parent; width: parent.width - 36
                visible: !statistics.historyMode && gameList.count === 0
                text: statistics.tr("Пока нет статистики\nЗапусти игру на PS3 — она появится здесь")
                color: statistics.colors.muted; font.pixelSize: 11
                horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
            }
            ListView {
                id: gameList; objectName: "gameStatisticsList"
                visible: !statistics.historyMode
                anchors.fill: parent; spacing: 8; clip: true
                model: statistics.statisticsModel
                ScrollBar.vertical: ScrollBar { }
                delegate: Rectangle {
                    required property int index
                    required property string title
                    required property string coverUrl
                    required property string playtime
                    required property int sessionCount
                    required property bool isCurrent
                    required property bool isPaused
                    required property string lastPlayed
                    id: gameRow
                    objectName: "statisticsGameRow" + index
                    width: gameList.width; height: statistics.gameCardHeight; radius: 3
                    color: statistics.colors.surface
                    border.color: isCurrent ? statistics.colors.accentBorder : statistics.colors.border
                    RowLayout {
                        anchors.fill: parent; anchors.margins: 8; spacing: 8
                        Rectangle {
                            Layout.preferredWidth: 48; Layout.preferredHeight: 48
                            color: statistics.colors.tile; radius: 3; clip: true
                            Image {
                                id: coverPicture
                                objectName: "statisticsCover" + gameRow.index
                                anchors.fill: parent; anchors.margins: 2
                                source: gameRow.coverUrl || "../assets/dualshock3.png"
                                sourceSize: gameRow.coverUrl ? Qt.size(160, 160) : Qt.size(256, 256)
                                sourceClipRect: gameRow.coverUrl ? undefined : Qt.rect(1, 54, 254, 156)
                                fillMode: Image.PreserveAspectFit; asynchronous: true; cache: true; smooth: true
                                readonly property bool imageReady: status === Image.Ready
                            }
                            Label { anchors.centerIn: parent; text: "PS3"; visible: coverPicture.status === Image.Error; color: statistics.colors.soft; font.pixelSize: 16 }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true; spacing: 4
                            Label { objectName: "statisticsGameTitle" + gameRow.index; text: gameRow.title; color: statistics.colors.text; font.pixelSize: 14; font.weight: Font.DemiBold; Layout.fillWidth: true; elide: Text.ElideRight }
                            RowLayout {
                                Layout.fillWidth: true
                                Label { text: gameRow.playtime; color: statistics.colors.accent; font.family: "Cascadia Mono"; font.pixelSize: 17; font.weight: Font.DemiBold }
                                Item { Layout.fillWidth: true }
                                Label { text: statistics.tr("Сессий: ") + gameRow.sessionCount; color: statistics.colors.soft; font.pixelSize: 11 }
                            }
                            Label {
                                text: gameRow.isCurrent ? statistics.tr("Сейчас в игре") : gameRow.isPaused ? statistics.tr("Подсчёт приостановлен · нет данных PSN") : statistics.tr("Последний запуск: ") + gameRow.lastPlayed
                                color: gameRow.isCurrent ? statistics.colors.accent : statistics.colors.muted
                                font.pixelSize: 11; Layout.fillWidth: true; elide: Text.ElideRight
                            }
                        }
                    }
                }
            }
            ListView {
                id: historyList; objectName: "sessionHistoryList"
                anchors.fill: parent; spacing: 10; clip: true
                visible: statistics.historyMode
                model: statistics.historyModel
                ScrollBar.vertical: ScrollBar { }
                delegate: Rectangle {
                    id: sessionRow
                    required property int index
                    required property string title
                    required property string coverUrl
                    required property string playtime
                    required property string startedAt
                    required property string endedAt
                    required property string state
                    required property bool isCurrent
                    required property bool isPaused
                    objectName: "sessionHistoryRow" + index
                    width: historyList.width; height: statistics.sessionCardHeight; radius: 3
                    color: statistics.colors.surface
                    border.color: isCurrent ? statistics.colors.accentBorder : statistics.colors.border
                    RowLayout {
                        anchors.fill: parent; anchors.margins: 8; spacing: 8
                        Rectangle {
                            Layout.preferredWidth: 48; Layout.preferredHeight: 48
                            color: statistics.colors.tile; radius: 3; clip: true
                            Image {
                                id: sessionCover
                                objectName: "sessionHistoryCover" + sessionRow.index
                                anchors.fill: parent; anchors.margins: 2
                                source: sessionRow.coverUrl || "../assets/dualshock3.png"
                                sourceSize: sessionRow.coverUrl ? Qt.size(160, 160) : Qt.size(256, 256)
                                sourceClipRect: sessionRow.coverUrl ? undefined : Qt.rect(1, 54, 254, 156)
                                fillMode: Image.PreserveAspectFit; asynchronous: true; cache: true; smooth: true
                                readonly property bool imageReady: status === Image.Ready
                            }
                            Label { anchors.centerIn: parent; text: "PS3"; visible: sessionCover.status === Image.Error; color: statistics.colors.soft; font.pixelSize: 16 }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true; spacing: 3
                            Label { text: sessionRow.title; color: statistics.colors.text; font.pixelSize: 14; font.weight: Font.DemiBold; Layout.fillWidth: true; elide: Text.ElideRight }
                            Label { objectName: "sessionHistoryDuration" + sessionRow.index; text: sessionRow.playtime; color: statistics.colors.accent; font.family: "Cascadia Mono"; font.pixelSize: 17; font.weight: Font.DemiBold }
                            Label { objectName: "sessionHistoryStart" + sessionRow.index; text: statistics.tr("Первая сессия: ") + sessionRow.startedAt; color: statistics.colors.soft; font.pixelSize: 10; Layout.fillWidth: true; wrapMode: Text.WordWrap }
                            Label { objectName: "sessionHistoryEnd" + sessionRow.index; text: statistics.tr("Последняя сессия: ") + (sessionRow.endedAt || "—"); color: statistics.colors.soft; font.pixelSize: 10; Layout.fillWidth: true; wrapMode: Text.WordWrap }
                            Label { objectName: "sessionHistoryState" + sessionRow.index; text: sessionRow.state; color: sessionRow.isCurrent && !sessionRow.isPaused ? statistics.colors.accent : statistics.colors.muted; font.pixelSize: 11; Layout.fillWidth: true; elide: Text.ElideRight }
                        }
                    }
                }
            }
            Label {
                objectName: "sessionHistoryEmpty"
                anchors.centerIn: parent; width: parent.width - 36
                visible: statistics.historyMode && historyList.count === 0
                text: statistics.tr("Подробная история появится после обнаружения игры в этой версии.\nСтарые часы сохранены во вкладке «Игры».")
                color: statistics.colors.muted; font.pixelSize: 11
                horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
            }
            // A soft edge signals more content without changing native scrolling.
            Rectangle {
                objectName: "statisticsTopFade"
                anchors.top: parent.top; width: parent.width; height: 24; z: 2
                visible: statistics.activeList.contentY > statistics.activeList.originY + 0.5
                gradient: Gradient {
                    GradientStop { position: 0; color: statistics.edgeColor }
                    GradientStop { position: 1; color: Qt.rgba(statistics.edgeColor.r, statistics.edgeColor.g, statistics.edgeColor.b, 0) }
                }
            }
            Rectangle {
                objectName: "statisticsBottomFade"
                anchors.bottom: parent.bottom; width: parent.width; height: 24; z: 2
                visible: statistics.activeList.contentY + statistics.activeList.height
                    < statistics.activeList.originY + statistics.activeList.contentHeight - 0.5
                gradient: Gradient {
                    GradientStop { position: 0; color: Qt.rgba(statistics.edgeColor.r, statistics.edgeColor.g, statistics.edgeColor.b, 0) }
                    GradientStop { position: 1; color: statistics.edgeColor }
                }
            }
        }
        Label {
            text: statistics.statusMessage || (statistics.historyMode ? statistics.tr("Показаны последние 100 сессий; все записи хранятся в базе. Длительность — наблюдаемое время, без сна и пропусков PSN.") : statistics.tr("Считается только наблюдаемое время при работающем приложении. Потеря PSN и сон компьютера не прибавляют игровое время."))
            color: statistics.statusMessage ? "#df8f79" : statistics.colors.muted
            font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.WordWrap
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 8
            Button {
                objectName: "statisticsTimeSortButton"
                visible: !statistics.historyMode
                text: statistics.tr("Время в игре") + (statistics.translator.statisticsSortMode === "playtime"
                    ? statistics.translator.statisticsSortAscending ? " ↑" : " ↓" : "")
                Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.minimumWidth: 0
                implicitHeight: 26
                onClicked: {
                    statistics.translator.sortStatisticsBy("playtime")
                    gameList.positionViewAtBeginning()
                }
                background: Rectangle { radius: 3; color: parent.down ? statistics.colors.secondaryPressed : statistics.colors.secondary; border.color: statistics.translator.statisticsSortMode === "playtime" ? statistics.colors.accentBorder : statistics.colors.border }
                contentItem: Label { text: parent.text; color: statistics.colors.text; font.pixelSize: 11; elide: Text.ElideRight; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
            }
            Button {
                objectName: "statisticsRecentSortButton"
                visible: !statistics.historyMode
                text: statistics.tr("Последний запуск") + (statistics.translator.statisticsSortMode === "lastPlayed"
                    ? statistics.translator.statisticsSortAscending ? " ↑" : " ↓" : "")
                Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.minimumWidth: 0
                implicitHeight: 26
                onClicked: {
                    statistics.translator.sortStatisticsBy("lastPlayed")
                    gameList.positionViewAtBeginning()
                }
                background: Rectangle { radius: 3; color: parent.down ? statistics.colors.secondaryPressed : statistics.colors.secondary; border.color: statistics.translator.statisticsSortMode === "lastPlayed" ? statistics.colors.accentBorder : statistics.colors.border }
                contentItem: Label { text: parent.text; color: statistics.colors.text; font.pixelSize: 11; elide: Text.ElideRight; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
            }
            Item { Layout.fillWidth: true; visible: statistics.historyMode }
            Button {
                objectName: "closeStatisticsButton"
                text: statistics.tr("Закрыть")
                Layout.minimumWidth: 80; Layout.preferredWidth: 80; Layout.maximumWidth: 80
                implicitWidth: 80; implicitHeight: 26
                onClicked: statistics.close()
                background: Rectangle { radius: 3; color: parent.down ? statistics.colors.secondaryPressed : statistics.colors.secondary; border.color: statistics.colors.border }
                contentItem: Label { text: parent.text; color: statistics.colors.text; font.pixelSize: 11; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
            }
        }
    }
}
