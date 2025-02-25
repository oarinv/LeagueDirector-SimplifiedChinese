import os
import sys
import json
import functools
import logging
import logging.handlers
import leaguedirector
from PySide2.QtGui import *
from PySide2.QtCore import *
from PySide2.QtWidgets import *
from PySide2.QtNetwork import *
from leaguedirector.widgets import *
from leaguedirector.sequencer import *
from leaguedirector.enable import *
from leaguedirector.api import Game, Playback, Render, Particles, Recording, Sequence
from leaguedirector.bindings import Bindings
from leaguedirector.settings import Settings


class SkyboxCombo(QComboBox):
    def showPopup(self):
        appDir = respath('skyboxes')
        userDir = userpath('skyboxes')
        paths = ['']
        paths += [os.path.join(appDir, f) for f in os.listdir(appDir) if f.endswith('.dds')]
        paths += [os.path.join(userDir, f) for f in os.listdir(userDir) if f.endswith('.dds')]
        self.clear()
        for path in sorted(paths):
            self.addItem(os.path.basename(path), path)
        QComboBox.showPopup(self)


class KeybindingsWindow(QScrollArea):
    def __init__(self, bindings):
        QScrollArea.__init__(self)
        self.fields = {}
        self.bindings = bindings
        self.setWidgetResizable(True)
        self.setWindowTitle('按键绑定')  # 原：'Key Bindings'
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        widget = QWidget()
        layout = QFormLayout()
        for name, value in self.bindings.getBindings().items():
            binding = HBoxWidget()
            field = QKeySequenceEdit(QKeySequence(value))
            field.keySequenceChanged.connect(functools.partial(self.edited, name, field))
            clear = QPushButton()
            clear.setToolTip('清除按键绑定')  # 原：'Clear Key Binding'
            clear.setFixedWidth(20)
            clear.setIcon(self.style().standardIcon(QStyle.SP_DialogCloseButton))
            clear.clicked.connect(functools.partial(self.clear, name, field))
            binding.addWidget(field)
            binding.addWidget(clear)
            layout.addRow(self.bindings.getLabel(name), binding)
            self.fields[name] = field
        reset = QPushButton('重置为默认值')  # 原：'Reset To Defaults'
        reset.clicked.connect(self.reset)
        layout.addRow('', reset)
        widget.setLayout(layout)
        self.setWidget(widget)

    def reset(self):
        for name, default in self.bindings.defaults.items():
            sequence = QKeySequence(default)
            self.fields[name].setKeySequence(sequence)
            self.bindings.setBinding(name, sequence)

    def clear(self, name, field):
        field.clear()
        self.bindings.setBinding(name, field.keySequence())

    def edited(self, name, field, *args):
        self.bindings.setBinding(name, field.keySequence())


class VisibleWindow(QScrollArea):
    options = [
        ('fogOfWar', 'show_fog_of_war', '显示战争迷雾？'),
        ('outlineSelect', 'show_selected_outline', '显示选中轮廓？'),
        ('outlineHover', 'show_hover_outline', '显示悬停轮廓？'),
        ('floatingText', 'show_floating_text', '显示浮动文本？'),
        ('interfaceAll', 'show_interface_all', '显示用户界面？'),
        ('interfaceReplay', 'show_interface_replay', '显示回放界面？'),
        ('interfaceScore', 'show_interface_score', '显示分数界面？'),
        ('interfaceScoreboard', 'show_interface_scoreboard', '显示记分板界面？'),
        ('interfaceFrames', 'show_interface_frames', '显示界面框架？'),
        ('interfaceMinimap', 'show_interface_minimap', '显示小地图界面？'),
        ('interfaceTimeline', 'show_interface_timeline', '显示时间线界面？'),
        ('interfaceChat', 'show_interface_chat', '显示聊天界面？'),
        ('interfaceTarget', 'show_interface_target', '显示目标界面？'),
        ('interfaceQuests', 'show_interface_quests', '显示任务界面？'),
        ('interfaceAnnounce', 'show_interface_announce', '显示公告界面？'),
        ('interfaceKillCallouts', 'show_interface_killcallouts', '显示击杀提示？'),
        ('interfaceNeutralTimers', 'show_interface_neutraltimers', '显示中立计时器？'),
        ('healthBarChampions', 'show_healthbar_champions', '显示英雄生命条？'),
        ('healthBarStructures', 'show_healthbar_structures', '显示建筑生命条？'),
        ('healthBarWards', 'show_healthbar_wards', '显示守卫生命条？'),
        ('healthBarPets', 'show_healthbar_pets', '显示宠物生命条？'),
        ('healthBarMinions', 'show_healthbar_minions', '显示小兵生命条？'),
        ('environment', 'show_environment', '显示环境？'),
        ('characters', 'show_characters', '显示角色？'),
        ('particles', 'show_particles', '显示粒子效果？'),
        ('banners', 'show_banners', '显示旗帜？'),
    ]

    def __init__(self, api):
        QScrollArea.__init__(self)
        self.api = api
        self.api.render.updated.connect(self.update)
        self.api.connected.connect(self.connect)
        self.inputs = {}
        self.bindings = {}
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWindowTitle('可见性')  # 原：'Visibility'
        widget = QWidget()
        layout = QFormLayout()
        for name, binding, label in self.options:
            self.inputs[name] = BooleanInput()
            self.inputs[name].setValue(True)
            self.inputs[name].valueChanged.connect(functools.partial(self.api.render.set, name))
            self.bindings[binding] = name
            layout.addRow(label, self.inputs[name])
        widget.setLayout(layout)
        self.setWidget(widget)

    def connect(self):
        for name, field in self.inputs.items():
            self.api.render.set(name, field.value())

    def update(self):
        for name, field in self.inputs.items():
            field.setValue(self.api.render.get(name))

    def restoreSettings(self, data):
        for name, value in data.items():
            if name in self.inputs:
                self.inputs[name].update(value)
                self.api.render.set(name, value)

    def saveSettings(self):
        return {name:self.api.render.get(name) for name in self.inputs}

    def onKeybinding(self, name):
        if name in self.bindings:
            self.inputs[self.bindings[name]].toggle()


class RenderWindow(QScrollArea):
    def __init__(self, api):
        QScrollArea.__init__(self)
        self.api = api
        self.api.render.updated.connect(self.update)
        self.cameraMode = QLabel('')
        self.cameraLockX = BooleanInput('X')
        self.cameraLockY = BooleanInput('Y')
        self.cameraLockZ = BooleanInput('Z')
        self.cameraPosition = VectorInput()
        self.cameraPosition.setSingleStep(10)
        self.cameraRotation = VectorInput([0, -90, -90], [360, 90, 90])
        self.cameraAttached = BooleanInput()
        self.cameraMoveSpeed = FloatInput(0, 5000)
        self.cameraMoveSpeed.setRelativeStep(0.1)
        self.cameraLookSpeed = FloatInput(0.01, 5)
        self.cameraLookSpeed.setSingleStep(0.01)
        self.fieldOfView = FloatInput(0, 180)
        self.nearClip = FloatInput()
        self.nearClip.setRelativeStep(0.05)
        self.farClip = FloatInput()
        self.farClip.setRelativeStep(0.05)
        self.navGrid = FloatInput(-100, 100)
        self.skyboxes = SkyboxCombo()
        self.skyboxRotation = FloatInput(-180, 180)
        self.skyboxOffset = FloatInput(-10000000, 10000000)
        self.skyboxRadius = FloatInput(0, 10000000)
        self.skyboxRadius.setSingleStep(10)
        self.sunDirection = VectorInput()
        self.sunDirection.setSingleStep(0.1)
        self.depthFogEnabled = BooleanInput()
        self.depthFogStart = FloatInput(0, 100000)
        self.depthFogStart.setRelativeStep(0.05)
        self.depthFogEnd = FloatInput(0, 100000)
        self.depthFogEnd.setRelativeStep(0.05)
        self.depthFogIntensity = FloatInput(0, 1)
        self.depthFogIntensity.setSingleStep(0.05)
        self.depthFogColor = ColorInput()
        self.heightFogEnabled = BooleanInput()
        self.heightFogStart = FloatInput(-100000, 100000)
        self.heightFogStart.setSingleStep(100)
        self.heightFogEnd = FloatInput(-100000, 100000)
        self.heightFogEnd.setSingleStep(100)
        self.heightFogIntensity = FloatInput(0, 1)
        self.heightFogIntensity.setSingleStep(0.05)
        self.heightFogColor = ColorInput()
        self.depthOfFieldEnabled = BooleanInput()
        self.depthOfFieldDebug = BooleanInput()
        self.depthOfFieldCircle = FloatInput(0, 300)
        self.depthOfFieldWidth = FloatInput(0, 100000)
        self.depthOfFieldWidth.setSingleStep(100)
        self.depthOfFieldNear = FloatInput(0, 100000)
        self.depthOfFieldNear.setRelativeStep(0.05)
        self.depthOfFieldMid = FloatInput(0, 100000)
        self.depthOfFieldMid.setRelativeStep(0.05)
        self.depthOfFieldFar = FloatInput(0, 100000)
        self.depthOfFieldFar.setRelativeStep(0.05)

        self.cameraLockX.valueChanged.connect(self.api.render.toggleCameraLockX)
        self.cameraLockY.valueChanged.connect(self.api.render.toggleCameraLockY)
        self.cameraLockZ.valueChanged.connect(self.api.render.toggleCameraLockZ)
        self.cameraPosition.valueChanged.connect(functools.partial(self.api.render.set, 'cameraPosition'))
        self.cameraRotation.valueChanged.connect(functools.partial(self.api.render.set, 'cameraRotation'))
        self.cameraAttached.valueChanged.connect(functools.partial(self.api.render.set, 'cameraAttached'))
        self.cameraMoveSpeed.valueChanged.connect(functools.partial(self.api.render.set, 'cameraMoveSpeed'))
        self.cameraLookSpeed.valueChanged.connect(functools.partial(self.api.render.set, 'cameraLookSpeed'))
        self.fieldOfView.valueChanged.connect(functools.partial(self.api.render.set, 'fieldOfView'))
        self.nearClip.valueChanged.connect(functools.partial(self.api.render.set, 'nearClip'))
        self.farClip.valueChanged.connect(functools.partial(self.api.render.set, 'farClip'))
        self.navGrid.valueChanged.connect(functools.partial(self.api.render.set, 'navGridOffset'))
        self.skyboxes.activated.connect(lambda index: self.api.render.set('skyboxPath', self.skyboxes.itemData(index)))
        self.skyboxRotation.valueChanged.connect(functools.partial(self.api.render.set, 'skyboxRotation'))
        self.skyboxRadius.valueChanged.connect(functools.partial(self.api.render.set, 'skyboxRadius'))
        self.skyboxOffset.valueChanged.connect(functools.partial(self.api.render.set, 'skyboxOffset'))
        self.sunDirection.valueChanged.connect(functools.partial(self.api.render.set, 'sunDirection'))
        self.depthFogEnabled.valueChanged.connect(functools.partial(self.api.render.set, 'depthFogEnabled'))
        self.depthFogStart.valueChanged.connect(functools.partial(self.api.render.set, 'depthFogStart'))
        self.depthFogEnd.valueChanged.connect(functools.partial(self.api.render.set, 'depthFogEnd'))
        self.depthFogIntensity.valueChanged.connect(functools.partial(self.api.render.set, 'depthFogIntensity'))
        self.depthFogColor.valueChanged.connect(functools.partial(self.api.render.set, 'depthFogColor'))
        self.heightFogEnabled.valueChanged.connect(functools.partial(self.api.render.set, 'heightFogEnabled'))
        self.heightFogStart.valueChanged.connect(functools.partial(self.api.render.set, 'heightFogStart'))
        self.heightFogEnd.valueChanged.connect(functools.partial(self.api.render.set, 'heightFogEnd'))
        self.heightFogIntensity.valueChanged.connect(functools.partial(self.api.render.set, 'heightFogIntensity'))
        self.heightFogColor.valueChanged.connect(functools.partial(self.api.render.set, 'heightFogColor'))
        self.depthOfFieldEnabled.valueChanged.connect(functools.partial(self.api.render.set, 'depthOfFieldEnabled'))
        self.depthOfFieldDebug.valueChanged.connect(functools.partial(self.api.render.set, 'depthOfFieldDebug'))
        self.depthOfFieldCircle.valueChanged.connect(functools.partial(self.api.render.set, 'depthOfFieldCircle'))
        self.depthOfFieldWidth.valueChanged.connect(functools.partial(self.api.render.set, 'depthOfFieldWidth'))
        self.depthOfFieldNear.valueChanged.connect(functools.partial(self.api.render.set, 'depthOfFieldNear'))
        self.depthOfFieldMid.valueChanged.connect(functools.partial(self.api.render.set, 'depthOfFieldMid'))
        self.depthOfFieldFar.valueChanged.connect(functools.partial(self.api.render.set, 'depthOfFieldFar'))

        widget = QWidget()
        layout = QFormLayout()
        layout.addRow('相机模式', self.cameraMode)  # 原：'Camera Mode'
        layout.addRow('相机锁定', HBoxWidget(self.cameraLockX, self.cameraLockY, self.cameraLockZ))  # 原：'Camera Lock'
        layout.addRow('相机位置', self.cameraPosition)  # 原：'Camera Position'
        layout.addRow('相机旋转', self.cameraRotation)  # 原：'Camera Rotation'
        layout.addRow('相机附着', self.cameraAttached)  # 原：'Camera Attached'
        layout.addRow('相机移动速度', self.cameraMoveSpeed)  # 原：'Camera Move Speed'
        layout.addRow('相机观察速度', self.cameraLookSpeed)  # 原：'Camera Look Speed'
        layout.addRow('视野范围', self.fieldOfView)  # 原：'Field of View'
        layout.addRow('近裁剪面', self.nearClip)  # 原：'Near Clip'
        layout.addRow('远裁剪面', self.farClip)  # 原：'Far Clip'
        layout.addRow('导航网格偏移', self.navGrid)  # 原：'Nav Grid Offset'
        layout.addRow(Separator())
        layout.addRow('天空盒', self.skyboxes)  # 原：'Skybox'
        layout.addRow('天空盒旋转', self.skyboxRotation)  # 原：'Skybox Rotation'
        layout.addRow('天空盒偏移', self.skyboxOffset)  # 原：'Skybox Offset'
        layout.addRow('天空盒半径', self.skyboxRadius)  # 原：'Skybox Radius'
        layout.addRow('太阳方向', self.sunDirection)  # 原：'Sun Direction'
        layout.addRow(Separator())
        layout.addRow('深度雾', self.depthFogEnabled)  # 原：'Depth Fog'
        layout.addRow('深度雾起点', self.depthFogStart)  # 原：'Depth Fog Start'
        layout.addRow('深度雾终点', self.depthFogEnd)  # 原：'Depth Fog End'
        layout.addRow('深度雾强度', self.depthFogIntensity)  # 原：'Depth Fog Intensity'
        layout.addRow('深度雾颜色', self.depthFogColor)  # 原：'Depth Fog Color'
        layout.addRow(Separator())
        layout.addRow('高度雾', self.heightFogEnabled)  # 原：'Height Fog'
        layout.addRow('高度雾起点', self.heightFogStart)  # 原：'Height Fog Start'
        layout.addRow('高度雾终点', self.heightFogEnd)  # 原：'Height Fog End'
        layout.addRow('高度雾强度', self.heightFogIntensity)  # 原：'Height Fog Intensity'
        layout.addRow('高度雾颜色', self.heightFogColor)  # 原：'Height Fog Color'
        layout.addRow(Separator())
        layout.addRow('景深', self.depthOfFieldEnabled)  # 原：'Depth of Field'
        layout.addRow('景深调试', self.depthOfFieldDebug)  # 原：'Depth of Field Debug'
        layout.addRow('景深圆形范围', self.depthOfFieldCircle)  # 原：'Depth of Field Circle'
        layout.addRow('景深宽度', self.depthOfFieldWidth)  # 原：'Depth of Field Width'
        layout.addRow('景深近距离', self.depthOfFieldNear)  # 原：'Depth of Field Near'
        layout.addRow('景深中距离', self.depthOfFieldMid)  # 原：'Depth of Field Mid'
        layout.addRow('景深远距离', self.depthOfFieldFar)  # 原：'Depth of Field Far'
        widget.setLayout(layout)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidget(widget)
        self.setWindowTitle('渲染')  # 原：'Rendering'

    def update(self):
        self.cameraLockX.update(self.api.render.cameraLockX is not None)
        self.cameraLockY.update(self.api.render.cameraLockY is not None)
        self.cameraLockZ.update(self.api.render.cameraLockZ is not None)
        self.cameraLockX.setCheckboxText('{0:.2f}'.format(self.api.render.cameraLockX) if self.api.render.cameraLockX else 'X')
        self.cameraLockY.setCheckboxText('{0:.2f}'.format(self.api.render.cameraLockY) if self.api.render.cameraLockY else 'Y')
        self.cameraLockZ.setCheckboxText('{0:.2f}'.format(self.api.render.cameraLockZ) if self.api.render.cameraLockZ else 'Z')
        self.cameraMode.setText(self.api.render.cameraMode)
        self.cameraPosition.update(self.api.render.cameraPosition)
        self.cameraRotation.update(self.api.render.cameraRotation)
        self.cameraAttached.update(self.api.render.cameraAttached)
        self.cameraMoveSpeed.update(self.api.render.cameraMoveSpeed)
        self.cameraLookSpeed.update(self.api.render.cameraLookSpeed)
        self.fieldOfView.update(self.api.render.fieldOfView)
        self.nearClip.update(self.api.render.nearClip)
        self.farClip.update(self.api.render.farClip)
        self.navGrid.update(self.api.render.navGridOffset)
        self.skyboxRotation.update(self.api.render.skyboxRotation)
        self.skyboxRadius.update(self.api.render.skyboxRadius)
        self.skyboxOffset.update(self.api.render.skyboxOffset)
        self.skyboxOffset.setRange(-self.api.render.skyboxRadius, self.api.render.skyboxRadius)
        self.skyboxOffset.setSingleStep(self.api.render.skyboxRadius / 1000)
        self.sunDirection.update(self.api.render.sunDirection)
        self.depthFogEnabled.update(self.api.render.depthFogEnabled)
        self.depthFogStart.update(self.api.render.depthFogStart)
        self.depthFogEnd.update(self.api.render.depthFogEnd)
        self.depthFogIntensity.update(self.api.render.depthFogIntensity)
        self.depthFogColor.update(self.api.render.depthFogColor)
        self.heightFogEnabled.update(self.api.render.heightFogEnabled)
        self.heightFogStart.update(self.api.render.heightFogStart)
        self.heightFogEnd.update(self.api.render.heightFogEnd)
        self.heightFogIntensity.update(self.api.render.heightFogIntensity)
        self.heightFogColor.update(self.api.render.heightFogColor)
        self.depthOfFieldEnabled.update(self.api.render.depthOfFieldEnabled)
        self.depthOfFieldDebug.update(self.api.render.depthOfFieldDebug)
        self.depthOfFieldCircle.update(self.api.render.depthOfFieldCircle)
        self.depthOfFieldWidth.update(self.api.render.depthOfFieldWidth)
        self.depthOfFieldNear.update(self.api.render.depthOfFieldNear)
        self.depthOfFieldMid.update(self.api.render.depthOfFieldMid)
        self.depthOfFieldFar.update(self.api.render.depthOfFieldFar)


class ParticlesWindow(VBoxWidget):
    def __init__(self, api):
        VBoxWidget.__init__(self)
        self.api = api
        self.api.particles.updated.connect(self.update)
        self.items = {}
        self.search = QLineEdit()
        self.search.setPlaceholderText('搜索...')  # 原：'Search...'
        self.search.textEdited.connect(self.textEdited)
        self.list = QListWidget()
        self.list.setSortingEnabled(True)
        self.list.itemChanged.connect(self.itemChanged)
        self.addWidget(self.search)
        self.addWidget(self.list)
        self.setWindowTitle('粒子')  # 原：'Particles'

    def textEdited(self, text):
        search = text.lower()
        for particle, item in self.items.items():
            if len(search) == 0 or search in particle.lower():
                item.setHidden(False)
            else:
                item.setHidden(True)

    def itemChanged(self, item):
        particle = item.text()
        enabled = item.checkState() == Qt.Checked
        if enabled != self.api.particles.getParticle(particle):
            self.api.particles.setParticle(particle, enabled)

    def update(self):
        for particle, enabled in self.api.particles.items():
            if particle not in self.items:
                item = QListWidgetItem(particle)
                item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                item.setBackground(QApplication.palette().toolTipBase())
                self.list.addItem(item)
                self.items[particle] = item
            self.items[particle].setCheckState(Qt.Checked if enabled else Qt.Unchecked)
        for particle in self.items.keys():
            if not self.api.particles.hasParticle(particle):
                self.list.removeItemWidget(self.items.pop(particle))

class RecordingWindow(VBoxWidget):
    def __init__(self, api):
        VBoxWidget.__init__(self)
        self.api = api
        self.api.recording.updated.connect(self.update)
        self.recordings = set()

        self.codec = QComboBox()
        self.codec.addItem('webm')
        self.codec.addItem('png')
        self.startTime = FloatInput(0, 100)
        self.endTime = FloatInput(0, 100)
        self.fps = FloatInput(0, 400)
        self.fps.setValue(60)
        self.lossless = BooleanInput()

        self.outputPath = userpath('recordings')
        self.outputLabel = QLabel()
        self.outputLabel.setTextFormat(Qt.RichText)
        self.outputLabel.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.outputLabel.setOpenExternalLinks(True)

        self.outputButton = QPushButton()
        self.outputButton.setToolTip('更改输出目录')  # 原：'Change Output Directory'
        self.outputButton.setFixedWidth(30)
        self.outputButton.setIcon(self.style().standardIcon(QStyle.SP_FileDialogStart))
        self.outputButton.clicked.connect(self.selectOutputDirectory)

        self.button = QPushButton('录制')  # 原：'Record'
        self.button.clicked.connect(self.startRecording)
        self.button2 = QPushButton('录制序列')  # 原：'Record Sequence'
        self.button2.clicked.connect(self.recordSequence)
        self.list = QListWidget()
        self.list.setSortingEnabled(True)
        self.list.itemDoubleClicked.connect(self.openRecording)

        self.form = QWidget(self)
        self.formLayout = QFormLayout(self.form)
        self.formLayout.addRow('编码格式', self.codec)  # 原：'Codec'
        self.formLayout.addRow('开始时间', self.startTime)  # 原：'Start Time'
        self.formLayout.addRow('结束时间', self.endTime)  # 原：'End Time'
        self.formLayout.addRow('每秒帧数', self.fps)  # 原：'Frames Per Second'
        self.formLayout.addRow('无损编码', self.lossless)  # 原：'Lossless Encoding'
        self.formLayout.addRow('输出目录', HBoxWidget(self.outputButton, self.outputLabel))  # 原：'Output Directory'
        self.formLayout.addRow(HBoxWidget(self.button, self.button2))
        self.formLayout.addRow(self.list)
        self.form.setLayout(self.formLayout)

        self.render = QWidget(self)
        self.progress = QProgressBar()
        self.cancel = QPushButton('取消录制')  # 原：'Cancel Recording'
        self.cancel.clicked.connect(self.stopRecording)
        self.renderLayout = QFormLayout()
        self.renderLayout.addRow(QLabel('正在渲染视频...'))  # 原：'Rendering video...'
        self.renderLayout.addRow(self.progress)
        self.renderLayout.addRow(self.cancel)
        self.render.setLayout(self.renderLayout)

        self.addWidget(self.form)
        self.addWidget(self.render)
        self.setWindowTitle('录制')  # 原：'Recording'

    def update(self):
        self.startTime.setRange(0, self.api.playback.length)
        self.endTime.setRange(0, self.api.playback.length)
        self.render.setVisible(self.api.recording.recording)
        self.form.setVisible(not self.api.recording.recording)
        if self.api.recording.recording:
            self.progress.setMinimum(self.api.recording.startTime * 1000)
            self.progress.setMaximum(self.api.recording.endTime * 1000)
            self.progress.setValue(self.api.recording.currentTime * 1000)
            if self.api.recording.path not in self.recordings:
                self.list.addItem(self.api.recording.path)
                self.recordings.add(self.api.recording.path)

    def selectOutputDirectory(self):
        self.setOutputDirectory(QFileDialog.getExistingDirectory(self, '选择输出目录', self.outputPath))  # 原：'Select Output Directory'

    def openRecording(self, item):
        QDesktopServices.openUrl(QUrl('file:///{}'.format(item.text())))

    def stopRecording(self):
        self.api.recording.update({'recording' : False})

    def startRecording(self):
        self.api.playback.play()
        self.api.recording.update({
            'recording' : True,
            'codec' : self.codec.currentText(),
            'startTime' : self.startTime.value(),
            'endTime' : self.endTime.value(),
            'framesPerSecond' : self.fps.value(),
            'enforceFrameRate' : True,
            'lossless' : self.lossless.value(),
            'path' : self.outputPath,
        })

    def setOutputDirectory(self, path):
        if os.path.exists(path):
            self.outputPath = path
            self.outputLabel.setText("<a href=\"file:///{}\">{}</a>".format(path, path))

    def recordSequence(self):
        self.api.sequence.setSequencing(True)
        self.startTime.setValue(self.api.sequence.startTime)
        self.endTime.setValue(self.api.sequence.endTime)
        self.startRecording()

    def saveSettings(self):
        return {'output': self.outputPath}

    def restoreSettings(self, data):
        self.setOutputDirectory(data.get('output', self.outputPath))

class TimelineWindow(QWidget):
    def __init__(self, api):
        QWidget.__init__(self)
        self.api = api
        self.api.playback.updated.connect(self.update)
        self.api.sequence.updated.connect(self.update)
        self.timer = schedule(10, self.animate)
        self.sequenceHeaders = SequenceHeaderView(self.api)
        self.sequenceTracks = SequenceTrackView(self.api, self.sequenceHeaders)
        layout = QVBoxLayout()
        self.layoutSpeed(layout)
        self.layoutTimeButtons(layout)
        self.layoutSlider(layout)
        self.layoutSequencer(layout)
        self.setWindowTitle('时间线')  # 原：'Timeline'
        self.setLayout(layout)

    def saveSettings(self):
        return {'directory': self.api.sequence.directory}

    def restoreSettings(self, data):
        self.api.sequence.setDirectory(data.get('directory', userpath('sequences')))

    def selectDirectory(self):
        self.api.sequence.setDirectory(QFileDialog.getExistingDirectory(self, '选择目录', self.api.sequence.directory))  # 原：'Select Directory'

    def layoutSequencer(self, layout):
        self.sequenceCombo = SequenceCombo(self.api)
        self.sequenceButton = QPushButton()
        self.sequenceButton.setToolTip('打开目录')  # 原：'Open Directory'
        self.sequenceButton.setFixedWidth(30)
        self.sequenceButton.setIcon(self.style().standardIcon(QStyle.SP_FileDialogStart))
        self.sequenceButton.clicked.connect(self.selectDirectory)
        layout.addWidget(HBoxWidget(self.sequenceCombo, self.sequenceButton))

        widget = HBoxWidget()
        self.applySequence = BooleanInput('应用序列？')  # 原：'Apply Sequence?'
        self.applySequence.valueChanged.connect(self.api.sequence.setSequencing)
        widget.addWidget(self.applySequence)
        playSequence = QPushButton('播放序列')  # 原：'Play Sequence'
        playSequence.setMaximumWidth(150)
        playSequence.clicked.connect(self.playSequence)
        widget.addWidget(playSequence)
        copySequence = QPushButton('复制序列')  # 原：'Copy Sequence'
        copySequence.setMaximumWidth(150)
        copySequence.clicked.connect(self.copySequence)
        widget.addWidget(copySequence)
        newSequence = QPushButton('新建序列')  # 原：'New Sequence'
        newSequence.setMaximumWidth(150)
        newSequence.clicked.connect(self.newSequence)
        widget.addWidget(newSequence)
        layout.addWidget(widget)

        widget = HBoxWidget()
        widget.addWidget(self.sequenceHeaders)
        widget.addWidget(self.sequenceTracks)
        layout.addWidget(widget)

        sequenceSelection = SequenceSelectedView(self.api, self.sequenceTracks)
        layout.addWidget(sequenceSelection)

    def layoutSpeed(self, layout):
        widget = HBoxWidget()
        self.play = QPushButton("")
        self.play.clicked.connect(self.api.playback.togglePlay)
        widget.addWidget(self.play)
        self.speed = FloatSlider('速度')  # 原：'Speed'
        self.speed.setRange(0, 8.0)
        self.speed.setSingleStep(0.1)
        self.speed.valueChanged.connect(lambda: self.api.playback.setSpeed(self.speed.value()))
        widget.addWidget(self.speed)
        for speed in [0.5, 1, 2, 4]:
            button = QPushButton("x{}".format(speed))
            button.setMaximumWidth(35)
            button.clicked.connect(functools.partial(self.api.playback.setSpeed, speed))
            widget.addWidget(button)
        layout.addWidget(widget)

    def layoutTimeButtons(self, layout):
        widget = HBoxWidget()
        for delta in [-120, -60, -30, -10, -5, 5, 10, 30, 60, 120]:
            sign = '+' if delta > 0 else ''
            button = QPushButton('{}{}秒'.format(sign, delta))  # 原：'{}{}s'
            button.setMinimumWidth(40)
            button.clicked.connect(functools.partial(self.api.playback.adjustTime, delta))
            widget.addWidget(button)
        layout.addWidget(widget)

    def layoutSlider(self, layout):
        widget = VBoxWidget()
        self.timeLabel = QLabel("")
        self.timeSlider = QSlider(Qt.Horizontal)
        self.timeSlider.setTickPosition(QSlider.TicksBelow)
        self.timeSlider.setTickInterval(60000)
        self.timeSlider.setTracking(False)
        self.timeSlider.sliderReleased.connect(self.onTimeline)
        widget.addWidget(self.timeLabel)
        widget.addWidget(self.timeSlider)
        layout.addWidget(widget)

    def onTimeline(self):
        self.api.playback.time = self.timeSlider.sliderPosition() / 1000

    def newSequence(self):
        name, ok = QInputDialog.getText(self, '创建新序列', '请输入序列名称')  # 原：'Create New Sequence', 'Enter a name for your sequence'
        if ok:
            self.api.sequence.create(name)

    def copySequence(self):
        name, ok = QInputDialog.getText(self, '复制序列', '请输入新序列的名称以保存副本')  # 原：'Copy Sequence', 'Enter a name to save a new copy of your sequence'
        if ok:
            self.api.sequence.copy(name)

    def playSequence(self):
        self.api.sequence.setSequencing(True)
        self.api.playback.play(self.api.sequence.startTime)

    def onKeybinding(self, name):
        if name == 'sequence_del_kf':
            self.sequenceTracks.deleteSelectedKeyframes()
        elif name == 'sequence_next_kf':
            self.sequenceTracks.selectNextKeyframe()
        elif name == 'sequence_prev_kf':
            self.sequenceTracks.selectPrevKeyframe()
        elif name == 'sequence_adj_kf':
            self.sequenceTracks.selectAdjacentKeyframes()
        elif name == 'sequence_all_kf':
            self.sequenceTracks.selectAllKeyframes()
        elif name == 'sequence_seek_kf':
            self.sequenceTracks.seekSelectedKeyframe()
        elif name == 'sequence_apply':
            self.applySequence.toggle()
        elif name == 'sequence_play':
            self.playSequence()
        elif name == 'sequence_new':
            self.newSequence()
        elif name == 'sequence_copy':
            self.copySequence()
        elif name == 'sequence_clear':
            self.sequenceTracks.clearKeyframes()
        elif name == 'sequence_undo':
            self.api.sequence.undo()
        elif name == 'sequence_redo':
            self.api.sequence.redo()
        elif name == 'kf_position':
            self.sequenceTracks.addKeyframe('cameraPosition')
        elif name == 'kf_rotation':
            self.sequenceTracks.addKeyframe('cameraRotation')
        elif name == 'kf_speed':
            self.sequenceTracks.addKeyframe('playbackSpeed')
        elif name == 'kf_fov':
            self.sequenceTracks.addKeyframe('fieldOfView')
        elif name == 'kf_near_clip':
            self.sequenceTracks.addKeyframe('nearClip')
        elif name == 'kf_far_clip':
            self.sequenceTracks.addKeyframe('farClip')
        elif name == 'kf_nav_grid':
            self.sequenceTracks.addKeyframe('navGridOffset')
        elif name == 'kf_sky_rotation':
            self.sequenceTracks.addKeyframe('skyboxRotation')
        elif name == 'kf_sky_radius':
            self.sequenceTracks.addKeyframe('skyboxRadius')
        elif name == 'kf_sky_offset':
            self.sequenceTracks.addKeyframe('skyboxOffset')
        elif name == 'kf_sun_direction':
            self.sequenceTracks.addKeyframe('sunDirection')
        elif name == 'kf_depth_fog_enable':
            self.sequenceTracks.addKeyframe('depthFogEnabled')
        elif name == 'kf_depth_fog_start':
            self.sequenceTracks.addKeyframe('depthFogStart')
        elif name == 'kf_depth_fog_end':
            self.sequenceTracks.addKeyframe('depthFogEnd')
        elif name == 'kf_depth_fog_intensity':
            self.sequenceTracks.addKeyframe('depthFogIntensity')
        elif name == 'kf_depth_fog_color':
            self.sequenceTracks.addKeyframe('depthFogColor')
        elif name == 'kf_height_fog_enable':
            self.sequenceTracks.addKeyframe('heightFogEnabled')
        elif name == 'kf_height_fog_start':
            self.sequenceTracks.addKeyframe('heightFogStart')
        elif name == 'kf_height_fog_end':
            self.sequenceTracks.addKeyframe('heightFogEnd')
        elif name == 'kf_height_fog_intensity':
            self.sequenceTracks.addKeyframe('heightFogIntensity')
        elif name == 'kf_height_fog_color':
            self.sequenceTracks.addKeyframe('heightFogColor')
        elif name == 'kf_dof_enabled':
            self.sequenceTracks.addKeyframe('depthOfFieldEnabled')
        elif name == 'kf_dof_circle':
            self.sequenceTracks.addKeyframe('depthOfFieldCircle')
        elif name == 'kf_dof_width':
            self.sequenceTracks.addKeyframe('depthOfFieldWidth')
        elif name == 'kf_dof_near':
            self.sequenceTracks.addKeyframe('depthOfFieldNear')
        elif name == 'kf_dof_mid':
            self.sequenceTracks.addKeyframe('depthOfFieldMid')
        elif name == 'kf_dof_far':
            self.sequenceTracks.addKeyframe('depthOfFieldFar')

    def formatTime(self, t):
        minutes, seconds = divmod(t, 60)
        return '{0:02}:{1:05.2f}'.format(int(minutes), seconds)

    def animate(self):
        self.speed.update(self.api.playback.speed)
        self.timeSlider.setRange(0, self.api.playback.length * 1000)
        if self.timeSlider.isSliderDown():
            self.timeLabel.setText(self.formatTime(self.timeSlider.sliderPosition() / 1000))
        else:
            self.timeLabel.setText(self.formatTime(self.api.playback.currentTime))
            self.timeSlider.setValue(self.api.playback.currentTime * 1000)

    def update(self):
        self.applySequence.update(self.api.sequence.sequencing)
        if self.api.playback.seeking:
            self.play.setDisabled(True)
            self.play.setText('正在定位')  # 原：'Seeking'
        elif self.api.playback.paused:
            self.play.setDisabled(False)
            self.play.setText('播放')  # 原：'Play'
        else:
            self.play.setDisabled(False)
            self.play.setText('暂停')  # 原：'Pause'


class Api(QObject):
    connected = Signal()

    def __init__(self):
        QObject.__init__(self)
        self.wasConnected = False
        self.game = Game()
        self.render = Render()
        self.particles = Particles()
        self.playback = Playback()
        self.recording = Recording()
        self.sequence = Sequence(self.render, self.playback)
        self.game.updated.connect(self.updated)
        self.render.updated.connect(self.updated)
        self.particles.updated.connect(self.updated)
        self.playback.updated.connect(self.updated)
        self.recording.updated.connect(self.updated)

    def updated(self):
        if not self.wasConnected and self.game.connected:
            self.connected.emit()
        self.wasConnected = self.game.connected

    def update(self):
        self.game.update()
        self.render.update()
        self.particles.update()
        self.playback.update()
        self.recording.update()

    def onKeybinding(self, name):
        if name == 'camera_up':
            self.render.moveCamera(y=7)
        elif name == 'camera_down':
            self.render.moveCamera(y=-7)
        elif name == 'camera_move_speed_up':
            self.render.cameraMoveSpeed = self.render.cameraMoveSpeed * 1.2
        elif name == 'camera_move_speed_down':
            self.render.cameraMoveSpeed = self.render.cameraMoveSpeed * 0.8
        elif name == 'camera_look_speed_up':
            self.render.cameraLookSpeed = self.render.cameraLookSpeed * 1.1
        elif name == 'camera_look_speed_down':
            self.render.cameraLookSpeed = self.render.cameraLookSpeed * 0.9
        elif name == 'camera_yaw_left':
            self.render.rotateCamera(x=-1)
        elif name == 'camera_yaw_right':
            self.render.rotateCamera(x=1)
        elif name == 'camera_pitch_up':
            self.render.rotateCamera(y=-1)
        elif name == 'camera_pitch_down':
            self.render.rotateCamera(y=1)
        elif name == 'camera_roll_left':
            self.render.rotateCamera(z=1)
        elif name == 'camera_roll_right':
            self.render.rotateCamera(z=-1)
        elif name == 'camera_lock_x':
            self.render.toggleCameraLockX()
        elif name == 'camera_lock_y':
            self.render.toggleCameraLockY()
        elif name == 'camera_lock_z':
            self.render.toggleCameraLockZ()
        elif name == 'camera_attach':
            self.render.cameraAttached = not self.render.cameraAttached
        elif name == 'camera_fov_up':
            self.render.fieldOfView = self.render.fieldOfView * 1.05
        elif name == 'camera_fov_down':
            self.render.fieldOfView = self.render.fieldOfView * 0.95
        elif name == 'render_dof_near_up':
            self.render.depthOfFieldNear = self.render.depthOfFieldNear * 1.05
        elif name == 'render_dof_near_down':
            self.render.depthOfFieldNear = self.render.depthOfFieldNear * 0.95
        elif name == 'render_dof_mid_up':
            self.render.depthOfFieldMid = self.render.depthOfFieldMid * 1.05
        elif name == 'render_dof_mid_down':
            self.render.depthOfFieldMid = self.render.depthOfFieldMid * 0.95
        elif name == 'render_dof_far_up':
            self.render.depthOfFieldFar = self.render.depthOfFieldFar * 1.05
        elif name == 'render_dof_far_down':
            self.render.depthOfFieldFar = self.render.depthOfFieldFar * 0.95
        elif name == 'play_pause':
            self.playback.paused = not self.playback.paused
        elif name == 'time_minus_120':
            self.playback.adjustTime(-120)
        elif name == 'time_minus_60':
            self.playback.adjustTime(-60)
        elif name == 'time_minus_30':
            self.playback.adjustTime(-30)
        elif name == 'time_minus_10':
            self.playback.adjustTime(-10)
        elif name == 'time_minus_5':
            self.playback.adjustTime(-5)
        elif name == 'time_plus_5':
            self.playback.adjustTime(5)
        elif name == 'time_plus_10':
            self.playback.adjustTime(10)
        elif name == 'time_plus_30':
            self.playback.adjustTime(30)
        elif name == 'time_plus_60':
            self.playback.adjustTime(60)
        elif name == 'time_plus_120':
            self.playback.adjustTime(120)


class ConnectWindow(QDialog):
    def __init__(self):
        QDialog.__init__(self)
        self.setWindowTitle('准备连接')  # 原：'Ready To Connect'
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.setWindowModality(Qt.WindowModal)
        self.welcome = QLabel()
        self.welcome.setText("""
            <h3>欢迎使用英雄联盟导演工具！</h3>  <!-- 原：Welcome to League Director! -->
            <p><a href="https://github.com/riotgames/leaguedirector/">https://github.com/riotgames/leaguedirector/</a></p>
            <p>首先，请确保您的游戏已启用<a href="https://developer.riotgames.com/replay-apis.html">回放API</a>，方法是在您的游戏安装旁边勾选相应选项。</p>  <!-- 原：First ensure your game has enabled the Replay API by checking the box next to your installation. -->
            <p>启用后，在《英雄联盟》客户端中启动一个回放，英雄联盟导演工具将自动连接。</p>  <!-- 原：Once enabled, start up a replay in the League of Legends client and League Director will automatically connect. -->
        """)
        self.welcome.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.welcome.setTextFormat(Qt.RichText)
        self.welcome.setOpenExternalLinks(True)
        self.layout.addWidget(self.welcome)
        self.list = QListWidget()
        self.list.itemChanged.connect(self.itemChanged)
        self.list.setSortingEnabled(False)
        self.layout.addWidget(self.list)
        self.reload()

    def sizeHint(self):
        return QSize(400, 100)

    def itemChanged(self, item):
        path = item.text()
        checked = item.checkState() == Qt.Checked
        if checked != isGameEnabled(path):
            setGameEnabled(path, checked)
            self.reload()

    def reload(self):
        self.list.clear()
        for path in findInstalledGames():
            enabled = isGameEnabled(path)
            item = QListWidgetItem(path)
            item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            item.setCheckState(Qt.Checked if enabled else Qt.Unchecked)
            item.setBackground(QApplication.palette().alternateBase())
            item.setStatusTip('你好！')  # 原：'Sup!'
            font = item.font()
            font.setPointSize(14)
            font.setBold(enabled)
            item.setFont(font)
            self.list.addItem(item)

class UpdateWindow(QDialog):
    def __init__(self):
        QDialog.__init__(self)
        self.setWindowTitle('有更新可用！')  # 原：'Update Available!'
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.setWindowModality(Qt.WindowModal)
        self.welcome = QLabel()
        self.welcome.setText("""
            <h3>英雄联盟导演工具的新版本已可用！</h3>  <!-- 原：A new version of League Director is available! -->
            <p><a href="https://github.com/riotgames/leaguedirector/releases/latest">https://github.com/riotgames/leaguedirector/releases/latest</a></p>
            <p>点击上面的链接下载最新版本。</p>  <!-- 原：Download the latest version by clicking the link above. -->
        """)
        self.welcome.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.welcome.setTextFormat(Qt.RichText)
        self.welcome.setOpenExternalLinks(True)
        self.layout.addWidget(self.welcome)


class LeagueDirector(object):
    def __init__(self):
        self.setupLogging()
        self.app = QApplication()
        self.setup()
        sys.exit(self.app.exec_())

    def setup(self):
        self.loadTheme()
        self.window = QMainWindow()
        self.mdi = QMdiArea()
        self.api = Api()
        self.windows = {}
        self.settings = Settings()
        self.bindings = self.setupBindings()
        self.addWindow(RenderWindow(self.api), 'render')
        self.addWindow(ParticlesWindow(self.api), 'particles')
        self.addWindow(VisibleWindow(self.api), 'visible')
        self.addWindow(TimelineWindow(self.api), 'timeline')
        self.addWindow(RecordingWindow(self.api), 'recording')
        self.addWindow(KeybindingsWindow(self.bindings), 'bindings')
        self.addWindow(ConnectWindow(), 'connect')
        self.addWindow(UpdateWindow(), 'update')
        self.window.setCentralWidget(self.mdi)
        self.window.setWindowTitle('英雄联盟导演工具')  # 原：'League Director'
        self.window.setWindowIcon(QIcon(respath('icon.ico')))
        self.window.closeEvent = self.closeEvent
        self.window.show()
        self.restoreSettings()
        self.checkUpdate()
        self.bindings.triggered.connect(self.api.onKeybinding)
        self.bindings.triggered.connect(self.windows['timeline'].onKeybinding)
        self.bindings.triggered.connect(self.windows['visible'].onKeybinding)
        self.timerUpdate = schedule(500, self.update)
        self.timerSave = schedule(5000, self.saveSettings)
        self.update()

    def closeEvent(self, event):
        self.saveSettings()
        QMainWindow.closeEvent(self.window, event)

    def setupLogging(self):
        logger = logging.getLogger()
        formatter = logging.Formatter('%(asctime)s [%(levelname)-8s] %(message)s')
        path = userpath('logs', 'leaguedirector.log')
        handler = logging.handlers.RotatingFileHandler(path, backupCount=20)
        try:
            handler.doRollover()
        except Exception: pass
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logging.info('启动英雄联盟导演工具 (%s)', leaguedirector.__version__)  # 原：'Started League Director (%s)'
        qInstallMessageHandler(self.handleMessage)

    def checkUpdate(self):
        self.updateAvailable = False
        request = QNetworkRequest(QUrl('https://api.github.com/repos/riotgames/leaguedirector/releases/latest'))
        response = self.api.game.manager().get(request)
        def callback():
            if response.error() == QNetworkReply.NoError:
                version = json.loads(response.readAll().data().decode()).get('tag_name')
                if version and version != 'v{}'.format(leaguedirector.__version__):
                    self.updateAvailable = True
        response.finished.connect(callback)

    def handleMessage(self, msgType, msgContext, msgString):
        if msgType == QtInfoMsg:
            logging.info('(QT) %s', msgString)
        elif msgType == QtDebugMsg:
            logging.debug('(QT) %s', msgString)
        elif msgType == QtWarningMsg:
            logging.warning('(QT) %s', msgString)
        elif msgType == QtCriticalMsg:
            logging.critical('(QT) %s', msgString)
        elif msgType == QtFatalMsg:
            logging.critical('(QT) %s', msgString)
        elif msgType == QtSystemMsg:
            logging.critical('(QT) %s', msgString)

    def setupBindings(self):
        return Bindings(self.window, self.settings.value('bindings', {}), [
            ('play_pause',                  '播放 / 暂停',                     'Space'),  # 原：'Play / Pause'
            ('camera_up',                   '相机向上',                        ''),       # 原：'Camera Up'
            ('camera_down',                 '相机向下',                        ''),       # 原：'Camera Down'
            ('camera_yaw_left',             '相机左偏航',                      ''),       # 原：'Camera Yaw Left'
            ('camera_yaw_right',            '相机右偏航',                      ''),       # 原：'Camera Yaw Right'
            ('camera_pitch_up',             '相机俯仰向上',                    ''),       # 原：'Camera Pitch Up'
            ('camera_pitch_down',           '相机俯仰向下',                    ''),       # 原：'Camera Pitch Down'
            ('camera_roll_left',            '相机左滚转',                      ''),       # 原：'Camera Roll Left'
            ('camera_roll_right',           '相机右滚转',                      ''),       # 原：'Camera Roll Right'
            ('camera_move_speed_up',        '相机移动速度增加',                'Ctrl++'), # 原：'Camera Move Speed Up'
            ('camera_move_speed_down',      '相机移动速度减少',                'Ctrl+-'), # 原：'Camera Move Speed Down'
            ('camera_look_speed_up',        '相机观察速度增加',                ''),       # 原：'Camera Look Speed Up'
            ('camera_look_speed_down',      '相机观察速度减少',                ''),       # 原：'Camera Look Speed Down'
            ('camera_lock_x',               '锁定相机X轴',                     ''),       # 原：'Camera Lock X Axis'
            ('camera_lock_y',               '锁定相机Y轴',                     ''),       # 原：'Camera Lock Y Axis'
            ('camera_lock_z',               '锁定相机Z轴',                     ''),       # 原：'Camera Lock Z Axis'
            ('camera_attach',               '相机附着',                        ''),       # 原：'Camera Attach'
            ('camera_fov_up',               '增加相机视野范围',                ''),       # 原：'Camera Increase Field of View'
            ('camera_fov_down',             '减少相机视野范围',                ''),       # 原：'Camera Decrease Field of View'
            ('render_dof_near_up',          '增加景深近距离',                  ''),       # 原：'Increase Depth of Field Near'
            ('render_dof_near_down',        '减少景深近距离',                  ''),       # 原：'Decrease Depth of Field Near'
            ('render_dof_mid_up',           '增加景深中距离',                  ''),       # 原：'Increase Depth of Field Mid'
            ('render_dof_mid_down',         '减少景深中距离',                  ''),       # 原：'Decrease Depth of Field Mid'
            ('render_dof_far_up',           '增加景深远距离',                  ''),       # 原：'Increase Depth of Field Far'
            ('render_dof_far_down',         '减少景深远距离',                  ''),       # 原：'Decrease Depth of Field Far'
            ('show_fog_of_war',             '显示战争迷雾',                    ''),       # 原：'Show Fog of War'
            ('show_selected_outline',       '显示选中轮廓',                    ''),       # 原：'Show Selected Outline'
            ('show_hover_outline',          '显示悬停轮廓',                    ''),       # 原：'Show Hover Outline'
            ('show_floating_text',          '显示浮动文本',                    ''),       # 原：'Show Floating Text'
            ('show_interface_all',          '显示所有用户界面',                ''),       # 原：'Show UI All'
            ('show_interface_replay',       '显示回放界面',                    ''),       # 原：'Show UI Replay'
            ('show_interface_score',        '显示分数界面',                    ''),       # 原：'Show UI Score'
            ('show_interface_scoreboard',   '显示记分板界面',                  ''),       # 原：'Show UI Scoreboard'
            ('show_interface_frames',       '显示界面框架',                    ''),       # 原：'Show UI Frames'
            ('show_interface_minimap',      '显示小地图界面',                  ''),       # 原：'Show UI Minimap'
            ('show_interface_timeline',     '显示时间线界面',                  ''),       # 原：'Show UI Timeline'
            ('show_interface_chat',         '显示聊天界面',                    ''),       # 原：'Show UI Chat'
            ('show_interface_target',       '显示目标界面',                    ''),       # 原：'Show UI Target'
            ('show_interface_quests',       '显示任务界面',                    ''),       # 原：'Show UI Quests'
            ('show_interface_announce',     '显示公告界面',                    ''),       # 原：'Show UI Announcements'
            ('show_healthbar_champions',    '显示英雄生命条',                  ''),       # 原：'Show Health Champions'
            ('show_healthbar_structures',   '显示建筑生命条',                  ''),       # 原：'Show Health Structures'
            ('show_healthbar_wards',        '显示守卫生命条',                  ''),       # 原：'Show Health Wards'
            ('show_healthbar_pets',         '显示宠物生命条',                  ''),       # 原：'Show Health Pets'
            ('show_healthbar_minions',      '显示小兵生命条',                  ''),       # 原：'Show Health Minions'
            ('show_environment',            '显示环境',                        ''),       # 原：'Show Environment'
            ('show_characters',             '显示角色',                        ''),       # 原：'Show Characters'
            ('show_particles',              '显示粒子效果',                    ''),       # 原：'Show Particles'
            ('sequence_play',               '播放序列',                        'Ctrl+Space'),  # 原：'Play Sequence'
            ('sequence_apply',              '应用序列',                        '\\'),     # 原：'Apply Sequence'
            ('sequence_new',                '新建序列',                        'Ctrl+N'), # 原：'New Sequence'
            ('sequence_copy',               '复制序列',                        ''),       # 原：'Copy Sequence'
            ('sequence_clear',              '清除序列',                        ''),       # 原：'Clear Sequence'
            ('sequence_del_kf',             '删除关键帧',                      'Del'),    # 原：'Delete Keyframe'
            ('sequence_next_kf',            '选择下一关键帧',                  ''),       # 原：'Select Next Keyframe'
            ('sequence_prev_kf',            '选择前一关键帧',                  ''),       # 原：'Select Prev Keyframe'
            ('sequence_adj_kf',             '选择相邻关键帧',                  ''),       # 原：'Select Adjacent Keyframes'
            ('sequence_all_kf',             '选择所有关键帧',                  'Ctrl+A'), # 原：'Select All Keyframes'
            ('sequence_seek_kf',            '跳转到关键帧',                    ''),       # 原：'Seek To Keyframe'
            ('sequence_undo',               '撤销序列操作',                    'Ctrl+Z'), # 原：'Sequence Undo'
            ('sequence_redo',               '重做序列操作',                    'Ctrl+Shift+Z'),  # 原：'Sequence Redo'
            ('time_minus_120',              '时间 -120秒',                     ''),       # 原：'Time -120 Seconds'
            ('time_minus_60',               '时间 -60秒',                      ''),       # 原：'Time -60 Seconds'
            ('time_minus_30',               '时间 -30秒',                      ''),       # 原：'Time -30 Seconds'
            ('time_minus_10',               '时间 -10秒',                      ''),       # 原：'Time -10 Seconds'
            ('time_minus_5',                '时间 -5秒',                       ''),       # 原：'Time -5 Seconds'
            ('time_plus_5',                 '时间 +5秒',                       ''),       # 原：'Time +5 Seconds'
            ('time_plus_10',                '时间 +10秒',                      ''),       # 原：'Time +10 Seconds'
            ('time_plus_30',                '时间 +30秒',                      ''),       # 原：'Time +30 Seconds'
            ('time_plus_60',                '时间 +60秒',                      ''),       # 原：'Time +60 Seconds'
            ('time_plus_120',               '时间 +120秒',                     ''),       # 原：'Time +120 Seconds'
            ('kf_position',                 '关键帧位置',                      '+'),      # 原：'Keyframe Position'
            ('kf_rotation',                 '关键帧旋转',                      '+'),      # 原：'Keyframe Rotation'
            ('kf_speed',                    '关键帧速度',                      ''),       # 原：'Keyframe Speed'
            ('kf_fov',                      '关键帧视野范围',                  ''),       # 原：'Keyframe Field of View'
            ('kf_near_clip',                '关键帧近裁剪面',                  ''),       # 原：'Keyframe Near Clip'
            ('kf_far_clip',                 '关键帧远裁剪面',                  ''),       # 原：'Keyframe Far Clip'
            ('kf_nav_grid',                 '关键帧导航网格偏移',              ''),       # 原：'Keyframe Nav Grid Offset'
            ('kf_sky_rotation',             '关键帧天空盒旋转',                ''),       # 原：'Keyframe Skybox Rotation'
            ('kf_sky_radius',               '关键帧天空盒半径',                ''),       # 原：'Keyframe Skybox Radius'
            ('kf_sky_offset',               '关键帧天空盒偏移',                ''),       # 原：'Keyframe Skybox Offset'
            ('kf_sun_direction',            '关键帧太阳方向',                  ''),       # 原：'Keyframe Sun Direction'
            ('kf_depth_fog_enable',         '关键帧深度雾启用',                ''),       # 原：'Keyframe Depth Fog Enable'
            ('kf_depth_fog_start',          '关键帧深度雾起点',                ''),       # 原：'Keyframe Depth Fog Start'
            ('kf_depth_fog_end',            '关键帧深度雾终点',                ''),       # 原：'Keyframe Depth Fog End'
            ('kf_depth_fog_intensity',      '关键帧深度雾强度',                ''),       # 原：'Keyframe Depth Fog Intensity'
            ('kf_depth_fog_color',          '关键帧深度雾颜色',                ''),       # 原：'Keyframe Depth Fog Color'
            ('kf_height_fog_enable',        '关键帧高度雾启用',                ''),       # 原：'Keyframe Height Fog Enable'
            ('kf_height_fog_start',         '关键帧高度雾起点',                ''),       # 原：'Keyframe Height Fog Start'
            ('kf_height_fog_end',           '关键帧高度雾终点',                ''),       # 原：'Keyframe Height Fog End'
            ('kf_height_fog_intensity',     '关键帧高度雾强度',                ''),       # 原：'Keyframe Height Fog Intensity'
            ('kf_height_fog_color',         '关键帧高度雾颜色',                ''),       # 原：'Keyframe Height Fog Color'
            ('kf_dof_enabled',              '关键帧景深启用',                  ''),       # 原：'Keyframe DOF Enabled'
            ('kf_dof_circle',               '关键帧景深圆形范围',              ''),       # 原：'Keyframe DOF Circle'
            ('kf_dof_width',                '关键帧景深宽度',                  ''),       # 原：'Keyframe DOF Width'
            ('kf_dof_near',                 '关键帧景深近距离',                ''),       # 原：'Keyframe DOF Near'
            ('kf_dof_mid',                  '关键帧景深中距离',                ''),       # 原：'Keyframe DOF Mid'
            ('kf_dof_far',                  '关键帧景深远距离',                ''),       # 原：'Keyframe DOF Far'
        ])

    def addWindow(self, widget, name):
        self.windows[name] = widget
        flags = Qt.Window | Qt.WindowTitleHint | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint
        self.mdi.addSubWindow(widget, flags)
        widget.update()

    def update(self):
        self.api.update()
        self.bindings.setGamePid(self.api.game.processID)
        for name, window in self.windows.items():
            if name == 'update':
                window.parent().setVisible(self.updateAvailable)
            elif name == 'connect':
                window.parent().setVisible(not self.api.game.connected)
            else:
                window.parent().setVisible(self.api.game.connected)

    def loadGeometry(self, widget, data):
        if data and len(data) == 4:
            widget.setGeometry(*data)

    def loadState(self, widget, data):
        if data is not None:
            widget.setWindowState(Qt.WindowStates(data))

    def restoreSettings(self):
        self.loadState(self.window, self.settings.value('window/state'))
        self.loadGeometry(self.window, self.settings.value('window/geo'))
        for name, widget in self.windows.items():
            parent = widget.parentWidget()
            self.loadState(parent, self.settings.value('{}/state'.format(name)))
            self.loadGeometry(parent, self.settings.value('{}/geo'.format(name)))
            if hasattr(widget, 'restoreSettings'):
                widget.restoreSettings(self.settings.value('{}/settings'.format(name), {}) or {})

    def saveSettings(self):
        self.settings.setValue('bindings', self.bindings.getBindings())
        self.settings.setValue('window/state', int(self.window.windowState()))
        self.settings.setValue('window/geo', self.window.geometry().getRect())
        for name, widget in self.windows.items():
            parent = widget.parentWidget()
            self.settings.setValue('{}/state'.format(name), int(parent.windowState()))
            self.settings.setValue('{}/geo'.format(name), parent.geometry().getRect())
            if hasattr(widget, 'saveSettings'):
                self.settings.setValue('{}/settings'.format(name), widget.saveSettings())

    def loadTheme(self):
        palette = QPalette()
        palette.setColor(QPalette.WindowText, QColor(180, 180, 180))
        palette.setColor(QPalette.Foreground, QColor(180, 180, 180))
        palette.setColor(QPalette.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.Light, QColor(80, 80, 80))
        palette.setColor(QPalette.Midlight, QColor(80, 80, 80))
        palette.setColor(QPalette.Mid, QColor(44, 44, 44))
        palette.setColor(QPalette.Dark, QColor(35, 35, 35))
        palette.setColor(QPalette.Text, QColor(190, 190, 190))
        palette.setColor(QPalette.BrightText, QColor(180, 180, 180))
        palette.setColor(QPalette.ButtonText, QColor(180, 180, 180))
        palette.setColor(QPalette.Base, QColor(42, 42, 42))
        palette.setColor(QPalette.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.Background, QColor(53, 53, 53))
        palette.setColor(QPalette.Shadow, QColor(20, 20, 20))
        palette.setColor(QPalette.Highlight, QColor(110, 125, 190))
        palette.setColor(QPalette.HighlightedText, QColor(180, 180, 180))
        palette.setColor(QPalette.PlaceholderText, QColor(180, 180, 180))
        palette.setColor(QPalette.Link, QColor(56, 252, 196))
        palette.setColor(QPalette.AlternateBase, QColor(66, 66, 66))
        palette.setColor(QPalette.ToolTipBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ToolTipText, QColor(180, 180, 180))
        palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(127, 127, 127))
        palette.setColor(QPalette.Disabled, QPalette.Text, QColor(127, 127, 127))
        palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(127, 127, 127))
        palette.setColor(QPalette.Disabled, QPalette.Highlight, QColor(80, 80, 80))
        palette.setColor(QPalette.Disabled, QPalette.HighlightedText, QColor(127, 127, 127))
        palette.setColor(QPalette.Disabled, QPalette.PlaceholderText, QColor(127, 127, 127))
        self.app.setPalette(palette)
        self.app.setStyle('Fusion')


if __name__ == '__main__':
    try:
        LeagueDirector()
    except Exception as exception:
        logging.exception(exception)