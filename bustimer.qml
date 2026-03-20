import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

ApplicationWindow {
    id: root
    width: 800
    height: 480
    visible: true
    title: "BusTimer"
    color: "#0d1117"

    readonly property color colBg:       "#0d1117"
    readonly property color colSurface:  "#161b22"
    readonly property color colBorder:   "#21262d"
    readonly property color colText:     "#e6edf3"
    readonly property color colMuted:    "#8b949e"
    readonly property color colGreen:    "#3fb950"
    readonly property color colAmber:    "#d29922"
    readonly property color colRed:      "#f85149"
    readonly property color colBlue:     "#58a6ff"

    readonly property int rowH: 197   // (480 - 56 header - 30 footer) / 2

    property string currentTime: Qt.formatTime(new Date(), "HH:mm")
    property string currentDate: Qt.formatDate(new Date(), "ddd d MMM")

    Timer {
        interval: 1000
        running: true
        repeat: true
        onTriggered: {
            root.currentTime = Qt.formatTime(new Date(), "HH:mm")
            root.currentDate = Qt.formatDate(new Date(), "ddd d MMM")
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ── Header ──────────────────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            height: 56
            color: colSurface

            RowLayout {
                anchors { fill: parent; leftMargin: 20; rightMargin: 20 }

                Text {
                    text: root.currentTime
                    font.pixelSize: 32
                    font.bold: true
                    color: colText
                }
                Text {
                    text: root.currentDate
                    font.pixelSize: 20
                    color: colMuted
                    Layout.alignment: Qt.AlignVCenter
                }
                Item { Layout.fillWidth: true }
                Text {
                    text: alertText
                    font.pixelSize: 15
                    color: colAmber
                    elide: Text.ElideRight
                    Layout.maximumWidth: 380
                    visible: text.length > 0
                }
                Rectangle {
                    width: 10; height: 10; radius: 5
                    color: (dataStatus === "OK") ? colGreen : colAmber
                }
            }

            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width; height: 1
                color: colBorder
            }
        }

        // ── Bus rows — show first 2 only ─────────────────────────────
        ListView {
            id: listView
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: busModel
            interactive: false   // no scrolling — only 2 rows shown
            clip: true

            delegate: Rectangle {
                width: listView.width
                // Only render first 2 rows; collapse the rest
                height: index < 2 ? root.rowH : 0
                visible: index < 2
                color: index === 0 ? colSurface : colBg

                // Left status stripe
                Rectangle {
                    width: 6
                    height: parent.height
                    color: statusColor(model.status)
                }

                RowLayout {
                    anchors { fill: parent; leftMargin: 20; rightMargin: 20 }
                    spacing: 0

                    // ── Bus side (left ~45%) ─────────────────────────
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.preferredWidth: parent.width * 0.45
                        spacing: 12
                        Layout.alignment: Qt.AlignVCenter

                        // Line badge
                        Rectangle {
                            width: 68; height: 48
                            radius: 8
                            color: colBlue
                            Layout.alignment: Qt.AlignVCenter
                            Text {
                                anchors.centerIn: parent
                                text: model.line
                                font.pixelSize: 21
                                font.bold: true
                                color: "#0d1117"
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 4
                            Layout.alignment: Qt.AlignVCenter

                            Text {
                                text: model.destination
                                font.pixelSize: 20
                                font.bold: true
                                color: colText
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                            // Bus countdown + time
                            RowLayout {
                                spacing: 8
                                Text {
                                    text: model.minutes <= 0 ? "Now" : model.minutes + " min"
                                    font.pixelSize: 30
                                    font.bold: true
                                    color: model.minutes <= 2 ? colAmber : colText
                                }
                                Text {
                                    text: model.busExpected
                                    font.pixelSize: 17
                                    color: colMuted
                                    Layout.alignment: Qt.AlignVCenter
                                }
                                Text {
                                    visible: model.busDelayMinutes > 0
                                    text: "+" + model.busDelayMinutes + "m late"
                                    font.pixelSize: 14
                                    color: colAmber
                                    Layout.alignment: Qt.AlignVCenter
                                }
                            }
                            // Change time — under bus countdown
                            Text {
                                visible: model.trainExpected.length > 0
                                text: model.changeMinutes + " min to change"
                                font.pixelSize: 15
                                color: statusColor(model.status)
                                font.bold: true
                            }
                        }
                    }

                    // ── Divider ──────────────────────────────────────
                    Rectangle {
                        width: 1; height: 80
                        color: colBorder
                        Layout.alignment: Qt.AlignVCenter
                        Layout.leftMargin: 8
                        Layout.rightMargin: 8
                    }

                    // ── Train side (right ~45%) ──────────────────────
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.preferredWidth: parent.width * 0.45
                        spacing: 5
                        Layout.alignment: Qt.AlignVCenter

                        // Line + departure time + delay
                        RowLayout {
                            spacing: 8
                            Text { text: "🚂"; font.pixelSize: 22 }
                            Text {
                                text: model.trainLine.length > 0 ? model.trainLine : "–"
                                font.pixelSize: 18
                                font.bold: true
                                color: colBlue
                            }
                            Text {
                                text: model.trainExpected.length > 0 ? model.trainExpected : "--:--"
                                font.pixelSize: 26
                                color: model.trainDelayMinutes > 0 ? colAmber : colMuted
                            }
                            Text {
                                visible: model.trainDelayMinutes > 0
                                text: "+" + model.trainDelayMinutes + "m"
                                font.pixelSize: 14
                                color: colAmber
                                font.bold: true
                                Layout.alignment: Qt.AlignVCenter
                            }
                        }

                        // Arrive at Stockholm C — headline
                        RowLayout {
                            spacing: 8
                            Text {
                                text: "Arrive " + model.arriveTime
                                font.pixelSize: 34
                                font.bold: true
                                color: model.arriveTime.length > 0 ? colText : colMuted
                            }
                        }

                        // "in X min at Stockholm C"
                        Text {
                            visible: model.arriveTime.length > 0
                            text: "in " + model.arriveMinutes + " min at Stockholm C"
                            font.pixelSize: 16
                            color: colMuted
                        }
                    }

                    // ── Status icon ──────────────────────────────────
                    Text {
                        text: statusIcon(model.status)
                        font.pixelSize: 44
                        font.bold: true
                        color: statusColor(model.status)
                        Layout.alignment: Qt.AlignVCenter
                        Layout.leftMargin: 8
                    }
                }

                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width; height: 1
                    color: colBorder
                }
            }

            // Empty / loading state
            Text {
                anchors.centerIn: parent
                visible: listView.count === 0
                text: dataStatus === "OK" ? "No departures found" : "Fetching…"
                font.pixelSize: 26
                color: colMuted
            }
        }

        // ── Footer ───────────────────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            height: 30
            color: colSurface

            Rectangle {
                anchors.top: parent.top
                width: parent.width; height: 1
                color: colBorder
            }
            Text {
                anchors.centerIn: parent
                text: "Slåttervägen → Jakobsberg / Barkarby  •  Updates every 30s"
                font.pixelSize: 13
                color: colMuted
            }
        }
    }

    function statusColor(status) {
        switch(status) {
            case 1: return colGreen
            case 2: return colAmber
            case 3: return colRed
            default: return colMuted
        }
    }

    function statusIcon(status) {
        switch(status) {
            case 1: return "✓"
            case 2: return "~"
            case 3: return "✗"
            default: return "?"
        }
    }
}
