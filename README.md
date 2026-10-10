# Map Reconstruction Radio-Map Dataset

本项目使用 OSM 建筑数据和 Sionna RT 构造静态、动态三维路径损耗数据集，用于后续从稀疏无线观测中重建场景。

当前已经实现的示例场景是北京古建筑区域：

```text
G:\Map_Reconstruction\Map_Reconstruction\beijing_temple
```

## 1. 完整数据处理流程

```text
OSM 原始地图
  ↓ clip_to_100m.py
100 m × 100 m 建筑平面及建筑高度
  ↓ export_sionna_scene.py
静态 Sionna 几何场景 scene.xml
  ├─→ run_static_gt.py
  │     静态路径损耗 L(z,y,x)
  └─→ build_dynamic_dataset.py
        600 个带运动物体的几何快照
          ↓ run_dynamic_gt.py
        动态路径损耗 L(t,z,y,x)，只保存 NPY
          ↓ render_dynamic_gt_png.py
        单独生成路径损耗 PNG
```

需要特别注意：

- 静态场景是 `beijing_temple\sionna\scene.xml` 及其 PLY 网格。
- 静态路径损耗是 `gt_Lxyz_z00to100_tx25\L_xyz.npy`。
- 静态转动态使用静态几何场景，不是把静态 `L_xyz.npy` 复制600次。
- 每个动态时刻必须重新执行射线追踪，才能得到正确的动态路径损耗。

## 2. 当前数据集统一设置

- 水平范围：100 m × 100 m。
- 垂直采样范围：0–100 m。
- x、y、z空间采样间隔均为1 m。
- 每帧形状：`[101,100,100]`，轴顺序为 `[z,y,x]`。
- 动态持续时间：60 s。
- 时间步长：0.1 s，即10 Hz。
- 动态帧数：600帧，时间为0.0–59.9 s。
- 频率：3.5 GHz。
- 发射机位置：`(50.0,50.0,25.5)` m。
- 每个接收高度射线样本数：200,000。
- 最大传播深度：3。
- 坐标原点为地图西南角，x向东、y向北、z向上。

动态物体：

- 12个人：长1 m、宽1 m、高2 m，速度0.4–1.8 m/s。
- 3辆车：长3 m、宽2 m、高2 m，速度0.8–4.0 m/s。
- 2架无人机：长宽高均为2 m，速度0.5–4.0 m/s，高度20–40 m。

轨迹通过有界加速度积分生成，位置和速度沿时间连续，并约束地图边界、建筑碰撞和物体间碰撞。

## 3. Windows CMD 运行环境

先进入项目根目录：

```bat
cd /d G:\Map_Reconstruction\Map_Reconstruction
```

Sionna环境：

```text
G:\Map_Reconstruction\sionna-env\Scripts\python.exe
```

`export_sionna_scene.py` 依赖 Shapely，应使用安装了 Shapely 的普通 Python；射线追踪使用 `sionna-env`。

## 4. 获得规定大小的静态地图

### 4.1 准备100 m × 100 m OSM

输入：

```text
beijing_temple\beijing_temple.osm
```

OSM的 `bounds` 应对应约100 m × 100 m区域，西南角映射为本地坐标 `(0,0)`。

若修改水平尺寸，需要同步修改：

- `clip_to_100m.py` 的边界检查与坐标映射。
- `export_sionna_scene.py` 的裁剪框和地面网格。
- `run_static_gt.py`、`build_dynamic_dataset.py`、`run_dynamic_gt.py` 的地图尺寸。

### 4.2 裁剪建筑并设置建筑高度

脚本：

```text
beijing_temple\clip_to_100m.py
```

运行：

```bat
python beijing_temple\clip_to_100m.py
```

输出：

```text
beijing_temple\beijing_temple_100m_buildings.geojson
```

该步骤裁剪建筑、转换本地米制坐标并写入 `height_m`。建筑高度由 `clip_to_100m.py` 中的 `HEIGHT` 字典决定：

```python
HEIGHT = {
    osm_id: (height_m, height_source, height_basis),
}
```

如果新OSM有可靠的 `height` 或 `building:levels` 标签，应优先使用标签。这里的 `height_m` 是建筑高度，不是接收点高度。

### 4.3 导出 Sionna 静态场景

```bat
python beijing_temple\export_sionna_scene.py
```

输出：

```text
beijing_temple\sionna\scene.xml
beijing_temple\sionna\manifest.json
beijing_temple\sionna\meshes\*.ply
```

脚本将建筑平面按 `height_m` 拉伸，并生成砖材质建筑、干燥地面和可加载的Sionna场景。

## 5. 生成静态路径损耗数据

脚本：

```text
beijing_temple\run_static_gt.py
```

运行：

```bat
G:\Map_Reconstruction\sionna-env\Scripts\python.exe beijing_temple\run_static_gt.py
```

输出：

```text
beijing_temple\gt_Lxyz_z00to100_tx25
```

包含 `L_xyz.npy`、`z.npy`、`meta.json`、各高度NPY和PNG。

### 5.1 设置静态垂直高度

在 `run_static_gt.py` 中修改：

```python
RX_Z_MIN = 0.0
RX_Z_MAX = 100.0
RX_Z_STEP = 1.0
```

层数为：

```text
(RX_Z_MAX - RX_Z_MIN) / RX_Z_STEP + 1
```

0–100 m、间隔1 m得到101层。水平参数：

```python
MAP_SIZE = [100.0,100.0]
CELL_SIZE = 1.0
```

所以 `L_xyz.shape=[101,100,100]`。

三个高度概念：

- 建筑高度：`clip_to_100m.py` 的 `HEIGHT`。
- 接收高度：`run_static_gt.py` 的 `RX_Z_*`。
- 发射机高度：`run_static_gt.py` 的 `TX_Z`，当前25.5 m。

## 6. 将静态几何转换为动态场景

脚本：

```text
beijing_temple\build_dynamic_dataset.py
```

运行：

```bat
G:\Map_Reconstruction\sionna-env\Scripts\python.exe beijing_temple\build_dynamic_dataset.py
```

默认输出：

```text
beijing_temple\dynamic_scene_dt0p1_large_objects
```

重新生成：

```bat
G:\Map_Reconstruction\sionna-env\Scripts\python.exe beijing_temple\build_dynamic_dataset.py --overwrite
```

动态参数：

```python
DT = 0.1
DURATION = 60.0
SEED = 20261010
SPECS = (...)
```

输出结构：

```text
dynamic_scene_dt0p1_large_objects\
  dataset.json
  index.csv
  trajectories.npz
  assets\
  frames\
    t0000_000.0s\
      scene.xml
      state.json
    ...
    t0599_059.9s\
      scene.xml
      state.json
```

每个时间点都是可独立加载的准静态场景。此步骤只生成动态几何，不执行射线追踪。

## 7. 对动态场景执行射线追踪

脚本：

```text
beijing_temple\run_dynamic_gt.py
```

该脚本只生成数值数据，不生成PNG。

单帧低采样测试：

```bat
G:\Map_Reconstruction\sionna-env\Scripts\python.exe beijing_temple\run_dynamic_gt.py --start-frame 0 --stop-frame 1 --z-min 0 --z-max 0 --samples-per-tx 1000 --output beijing_temple\dynamic_gt_smoke
```

正式运行600帧：

```bat
G:\Map_Reconstruction\sionna-env\Scripts\python.exe beijing_temple\run_dynamic_gt.py
```

默认输出：

```text
G:\Map_Reconstruction\Map_Reconstruction_Dataset\Map_Reconstruction\beijing_temple
```

数据集根目录结构：

```text
G:\Map_Reconstruction\Map_Reconstruction_Dataset\Map_Reconstruction\
  README.md
  render_dynamic_gt_png.py
  beijing_temple\
    run_config.json
    times_s.npy
    z_m.npy
    frames\
      t0000_000.0s\
        L_xyz.npy
        meta.json
      ...
  png\
```

每帧 `L_xyz.shape=[101,100,100]`，600帧共同表示 `L(t,z,y,x)`。

脚本逐帧、逐高度计算，完成帧自动跳过，当前帧高度层支持断点续算。

### 7.1 分批运行

```bat
G:\Map_Reconstruction\sionna-env\Scripts\python.exe beijing_temple\run_dynamic_gt.py --start-frame 0 --stop-frame 100
G:\Map_Reconstruction\sionna-env\Scripts\python.exe beijing_temple\run_dynamic_gt.py --start-frame 100 --stop-frame 200
```

帧范围左闭右开；中断后重新运行相同命令即可。

### 7.2 修改动态高度

```bat
G:\Map_Reconstruction\sionna-env\Scripts\python.exe beijing_temple\run_dynamic_gt.py --z-min 0 --z-max 100 --z-step 1
```

修改高度、网格、样本数或深度时，应使用新输出目录，避免配置混合。

## 8. 从动态 NPY 单独生成 PNG

源项目脚本：

```text
beijing_temple\render_dynamic_gt_png.py
```

数据集根目录也包含独立脚本：

```text
G:\Map_Reconstruction\Map_Reconstruction_Dataset\Map_Reconstruction\render_dynamic_gt_png.py
```

运行：

```bat
G:\Map_Reconstruction\sionna-env\Scripts\python.exe G:\Map_Reconstruction\Map_Reconstruction_Dataset\Map_Reconstruction\render_dynamic_gt_png.py
```

默认读取：

```text
G:\Map_Reconstruction\Map_Reconstruction_Dataset\Map_Reconstruction\beijing_temple
```

默认输出：

```text
G:\Map_Reconstruction\Map_Reconstruction_Dataset\Map_Reconstruction\png
```

只处理前10帧：

```bat
G:\Map_Reconstruction\sionna-env\Scripts\python.exe G:\Map_Reconstruction\Map_Reconstruction_Dataset\Map_Reconstruction\render_dynamic_gt_png.py --start-frame 0 --stop-frame 10
```

每隔10层出图：

```bat
G:\Map_Reconstruction\sionna-env\Scripts\python.exe G:\Map_Reconstruction\Map_Reconstruction_Dataset\Map_Reconstruction\render_dynamic_gt_png.py --png-every 10
```

默认颜色范围50–150 dB，可通过 `--vmin`、`--vmax` 修改。

## 9. 存储与内存

- 单帧float32 `L_xyz.npy` 约3.85 MiB。
- 600帧数值数据约2.26 GiB。
- 60,600张高度PNG预计约2.9 GiB。
- NPY和PNG合计约5.1 GiB，建议预留6–8 GiB。
- 200,000射线样本单层实测峰值内存约391 MiB。
- 逐帧处理不会将内存乘以600，建议至少预留2 GiB内存。
- `--keep-layers` 会额外占用约2.26 GiB。

## 10. 旧数据与当前数据

当前版本：

```text
动态几何：dynamic_scene_dt0p1_large_objects
射线结果：G:\Map_Reconstruction\Map_Reconstruction_Dataset\Map_Reconstruction\beijing_temple
图片结果：G:\Map_Reconstruction\Map_Reconstruction_Dataset\Map_Reconstruction\png
```

旧版本目录不可与当前结果混用：

```text
dynamic_scene_dt0p1
dynamic_gt_dt0p1_tx25
```

## 11. 后续多场景设计

10个场景应按无线传播影响因子选择：

- 建筑高度：低层、多层、高层。
- 平面布局：广场、街谷、校园、村落。
- 建筑密度与视距比例。
- 平地、坡地、滨水。
- 地面、土壤和简化植被。
- 不同发射机几何位置。
- 不同动态强度。
- 行人、车辆和作业无人机。
- 砖、混凝土、玻璃、金属等材料。
- 不同OSM高度数据完整度。