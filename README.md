# gesture-drawing2.0
In this warehouse, I will continue an interactive project. Turn on the camera, pinch with one hand to write on the black-and-white screen, and open the color window with both hands.
GESTURE-DRAWING



gesture-drawing



<主要作用>

基于手势识别（如 MediaPipe / OpenCV）的绘图工具，用手势在屏幕上绘画。
<Main Function>

A drawing tool based on gesture recognition (such as MediaPipe / OpenCV), allowing you to draw on the screen using gestures.


<功能特性>

\- 手势跟踪（手指关键点）

\- 绘图模式切换（食指画线，拳头擦除）

\- 支持颜色/粗细调整
<Features>

- Gesture tracking (finger key points)

- Drawing mode switch (index finger to draw, fist to erase)

- Supports color/thickness adjustment


<安装>

```bash

git clone https://github.com/你的用户名/gesture-drawing.git

cd gesture-drawing

pip install -r requirements.txt



<运行>

python main.py



<依赖>

Python 3.8+

OpenCV

MediaPipe（或其他手势库）



<使用说明>

摄像头开启后，伸出食指或捏合拇指食指进行绘画

\-画封闭的圆可以激活“太阳”图像

\-握拳表示移动光标（不画线）

\-胜利手势可以清屏

双手比框可以框出彩色相框

按 c 清屏，q 退出

<Instructions>

After the camera is turned on, extend your index finger or pinch your thumb and index finger to draw.

- Drawing a closed circle can activate the 'sun' image.

- Making a fist indicates moving the cursor (without drawing lines).

- A victory gesture can clear the screen.

Use both hands to form a frame to create a colorful frame.

Press 'c' to clear the screen, 'q' to quit.

<许可证>

\## 最后，添加到 Git



```bash

git add README.md

git commit -m "Add README.md"



