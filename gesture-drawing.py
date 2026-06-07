import cv2
import mediapipe as mp
import numpy as np
import random
import math
import time

# 基础参数
PINCH_THRESH = 38
brush_color = (200, 150, 0)
rect_line_color = (200, 150 , 180)
brush_thickness = 6

# 绘图状态
draw_last_point = None
draw_canvas = None
dynamic_rect = None
hue = 0 #色相初始状态
current_stroke_points = []  #储存当前笔画的所有点
was_drawing = False   # 上一帧是否在绘画
drawing = False

#光线特效初始参数
last_frame_time = time.time()   # 用于计算时间差（delta time）
ray_effects = []   # 存储光线特效对象

# 初始化双手手势
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    min_detection_confidence=0.7,
    min_tracking_confidence=0.5
)
mp_draw = mp.solutions.drawing_utils

cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

def is_victory_gesture(hand_landmarks):
    tip_ids = [8, 12, 16, 20]
    base_ids = [6, 10, 14, 18]
    index_extended = hand_landmarks[8].y < hand_landmarks[6].y
    middle_extended = hand_landmarks[12].y < hand_landmarks[10].y
    ring_bent = hand_landmarks[16].y > hand_landmarks[14].y
    pinky_bent = hand_landmarks[20].y > hand_landmarks[18].y
    return index_extended and middle_extended and ring_bent and pinky_bent

# 获取帧尺寸
ret, temp_frame = cap.read()
if not ret:
    print("摄像头打开失败")
    cap.release()
    exit()
img_h, img_w, _ = temp_frame.shape
draw_canvas = np.zeros((img_h, img_w, 3), dtype=np.uint8)

def clamp(val, min_v, max_v):
    return max(min_v, min(val, max_v))

prev_x, prev_y = 0, 0
drawing = False

# 清空延迟控制
last_clear_time = 0
CLEAR_COOLDOWN = 0.5   # 秒

# 封闭圆检测函数
def is_closed_circle(points, w, h):
    if len(points) < 10:
        return False
    # 起点终点距离
    start = points[0]
    end = points[-1]
    dist = np.hypot(start[0]-end[0], start[1]-end[1])
    if dist > 50:   # 闭合距离阈值，可调
        return False
    
    # 计算中心点（所有点平均）
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    # 计算所有点到中心的距离
    radii = [np.hypot(p[0]-cx, p[1]-cy) for p in points]
    mean_r = np.mean(radii)
    # 距离标准差 / 均值，越小越像圆
    if mean_r < 20:   # 半径太小忽略
        return False
    radius_std = np.std(radii)
    if radius_std / mean_r < 0.3:   # 偏差小于30%认为是圆，可调
        return True
    return False

#绘制金色圆环函数
def draw_golden_ring(canvas, points):
    # 计算圆心和半径
    cx = int(sum(p[0] for p in points) / len(points))
    cy = int(sum(p[1] for p in points) / len(points))
    radii = [np.hypot(p[0]-cx, p[1]-cy) for p in points]
    mean_r = int(np.mean(radii))
    # 金色 BGR: (0, 215, 255) 或 (0, 255, 255) 是黄色，金色可调
    gold_color = (0, 215, 255)   # 接近金色
    thickness = 4
    cv2.circle(canvas, (cx, cy), mean_r, gold_color, thickness)
    # 可选：画一个稍小的内圈，增强环效果
    cv2.circle(canvas, (cx, cy), max(2, mean_r-8), gold_color, thickness-2)



#静态金色圆环保留函数
def draw_golden_ring_static(canvas, center, radius):
    gold_color = (0, 215, 255)   # 金色
    thickness = 6
    cv2.circle(canvas, center, radius, gold_color, thickness)

#虚实光线绘制函数
def draw_dashed_line(img, start, end, color, thickness, dash_length=10, gap_length=6):
    """
    绘制虚线（可自定义 dash 和 gap 长度）
    如果希望长短线交织，可以在调用时传入不同的 dash_length 和 gap_length
    """
    x1, y1 = start
    x2, y2 = end
    length = np.hypot(x2 - x1, y2 - y1)
    if length == 0:
        return
    # 单位方向向量
    dx = (x2 - x1) / length
    dy = (y2 - y1) / length
    # 当前距离
    dist = 0
    draw = True
    while dist < length:
        if draw:
            # 画一段实线
            next_dist = min(dist + dash_length, length)
            p1 = (int(x1 + dx * dist), int(y1 + dy * dist))
            p2 = (int(x1 + dx * next_dist), int(y1 + dy * next_dist))
            cv2.line(img, p1, p2, color, thickness)
        dist += dash_length if draw else gap_length
        draw = not draw

#光线特效
def create_ray_effect(center, base_radius, num_rays=28):
    step = 2 * math.pi / num_rays
    angles = [i * step for i in range(num_rays)]
    random.shuffle(angles)          # 打乱顺序，让光线看起来随机
    rays = []
    for angle in angles:
        max_len = base_radius * random.uniform(2.0, 3.5)   # 最大长度 2~3.5 倍半径
        dash_len = random.choice([5, 8, 11, 14])           # 缩短虚线长度，适合短光线
        gap_len = random.choice([3, 5, 7])
        rays.append({
            'angle': angle,
            'max_len': max_len,
            'dash': dash_len,
            'gap': gap_len
        })
    return {
        'center': center,
        'base_radius': base_radius,
        'rays': rays,
        'start_time': time.time(),
        'anim_duration': 2.0,
        'hold_duration': 2.0
    }
#绘制光线
def draw_ray_effect(img, effect, current_time):
    elapsed = current_time - effect['start_time']
    total = effect['anim_duration'] + effect['hold_duration']
    if elapsed >= total:
        return False   # 特效结束
    
    # 计算当前光线长度系数
    if elapsed <= effect['anim_duration']:
        # 放射阶段：线性增长
        factor = elapsed / effect['anim_duration']
    else:
        # 保留阶段：保持最大长度
        factor = 1.0
    
    center = effect['center']
    base_r = effect['base_radius']
    for ray in effect['rays']:
        angle = ray['angle']
        max_len = ray['max_len']
        current_len = base_r + factor * (max_len - base_r)
        # 射线终点
        end_x = center[0] + math.cos(angle) * current_len
        end_y = center[1] + math.sin(angle) * current_len
        # 射线起点（圆环边缘）
        start_x = center[0] + math.cos(angle) * base_r
        start_y = center[1] + math.sin(angle) * base_r
        # 绘制虚线（长短交织）
        draw_dashed_line(img, (int(start_x), int(start_y)), (int(end_x), int(end_y)),
                         (0, 215, 255), 2, dash_length=ray['dash'], gap_length=ray['gap'])
    return True



while True:
#计算时间差
    current_time = time.time()
    dt = min(current_time - last_frame_time, 0.033)   # 限制最大 dt 0.033秒
    last_frame_time = current_time

    success, frame = cap.read()
    if not success:
        print("摄像头读取失败，等待重试...")
        time.sleep(0.1)
        cap.release()
        cap = cv2.VideoCapture(0)
        continue

    frame = cv2.flip(frame, 1)
    gray_img = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    black_white_bg = cv2.cvtColor(gray_img, cv2.COLOR_GRAY2BGR)

    rgb_input = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    hand_result = hands.process(rgb_input)

    hand_info = []
    dynamic_rect = None



    if hand_result.multi_hand_landmarks:
        for hand_lm in hand_result.multi_hand_landmarks:
            # 胜利手势清空画布（带延迟）
            if is_victory_gesture(hand_lm.landmark):
                now = time.time()
                if now - last_clear_time > CLEAR_COOLDOWN:
                    draw_canvas[:] = 0          # 清空画布
                    ray_effects = []
                    draw_last_point = None      # 重置上一个点，防止清空后本帧立即连线
                    print("胜利手势！画布已清空")
                    last_clear_time = now

            # 无论是否胜利手势，都收集拇指和食指坐标（用于后续绘画）
            thumb_pt = hand_lm.landmark[4]
            index_pt = hand_lm.landmark[8]
            tx = int(thumb_pt.x * img_w)
            ty = int(thumb_pt.y * img_h)
            ix = int(index_pt.x * img_w)
            iy = int(index_pt.y * img_h)
            hand_info.append((tx, ty, ix, iy))

    # 双手矩形绘制（当 hand_info 中有两只手的数据时）
    if len(hand_info) == 2:
        draw_last_point = None
        h1, h2 = hand_info[0], hand_info[1]
        all_x = [h1[0], h1[2], h2[0], h2[2]]
        all_y = [h1[1], h1[3], h2[1], h2[3]]
        x_min = clamp(min(all_x), 0, img_w-1)
        y_min = clamp(min(all_y), 0, img_h-1)
        x_max = clamp(max(all_x), 0, img_w-1)
        y_max = clamp(max(all_y), 0, img_h-1)
        if x_max > x_min and y_max > y_min:
            dynamic_rect = [(x_min, y_min), (x_max, y_max)]

    # 单手捏合绘画
    elif len(hand_info) == 1:
        dynamic_rect = None
        tx, ty, ix, iy = hand_info[0]
        pinch_dis = np.hypot(tx - ix, ty - iy)
        current_draw_pt = (ix, iy)
        was_drawing = drawing
        if pinch_dis < PINCH_THRESH:
            # 更新色相和颜色
            hue = (hue + 2) % 180
            hsv_color = np.uint8([[[hue, 255, 255]]])
            brush_color = tuple(cv2.cvtColor(hsv_color, cv2.COLOR_HSV2BGR)[0][0].tolist())

            if draw_last_point is not None:
                cv2.line(draw_canvas, draw_last_point, current_draw_pt, brush_color, brush_thickness)
                if not current_stroke_points or (abs(current_draw_pt[0]-current_stroke_points[-1][0])>5 or abs(current_draw_pt[1]-current_stroke_points[-1][1])>5):
                    current_stroke_points.append(current_draw_pt)
            draw_last_point = current_draw_pt
            drawing = True
        else:
                # 绘画结束
            if drawing:   # 上一帧在绘画，现在松开了
                if was_drawing:   # 确保是刚结束
            # 检测是否封闭圆
                   if is_closed_circle(current_stroke_points, img_w, img_h):
    # 计算圆心和半径（复用之前的计算）
                       cx = int(sum(p[0] for p in current_stroke_points) / len(current_stroke_points))
                       cy = int(sum(p[1] for p in current_stroke_points) / len(current_stroke_points))
                       radii = [np.hypot(p[0]-cx, p[1]-cy) for p in current_stroke_points]
                       mean_r = int(np.mean(radii))
    # 添加光线特效
                       draw_golden_ring_static(draw_canvas, (cx, cy), mean_r)
    # 2. 添加动态光线特效（临时）
                       ray_effects.append(create_ray_effect((cx, cy), mean_r, num_rays=12))
                       print("金色圆环 + 放射光线已触发")

        # 清空轨迹
                current_stroke_points = []
            draw_last_point = None
            drawing = False

    # 叠加画布并显示
    base_img = cv2.addWeighted(black_white_bg, 1, draw_canvas, 1, 0)
    # final_img
    final_img = base_img.copy()
    if dynamic_rect is not None:
        pt1, pt2 = dynamic_rect
        cv2.rectangle(final_img, pt1, pt2, rect_line_color, 6)
        roi = frame[pt1[1]:pt2[1], pt1[0]:pt2[0]]
        final_img[pt1[1]:pt2[1], pt1[0]:pt2[0]] = roi


# 绘制放射光线特效（不写入持久画布，只临时显示）
    current_time = time.time()
    remaining_rays = []
    for effect in ray_effects:
        if draw_ray_effect(final_img, effect, current_time):
            remaining_rays.append(effect)
    ray_effects = remaining_rays

    cv2.imshow("Gesture Program", final_img)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('g'):
        break
    if key == ord('c'):
        draw_canvas[:] = 0
        draw_last_point = None

cap.release()
cv2.destroyAllWindows()