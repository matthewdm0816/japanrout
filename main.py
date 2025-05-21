import geopandas
import matplotlib.pyplot as plt
from matplotlib import font_manager # For font handling
import matplotlib.patheffects as path_effects # For text outline
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
from shapely.geometry import Point
import time
import pandas as pd
import os
import json
from adjustText import adjust_text # <--- IMPORT adjustText

# --- 配置 (请根据您的设置修改) ---
# 1. Shapefile 路径
SHAPEFILE_PATH = r"ne_10m_admin_0_countries\ne_10m_admin_0_countries.shp"  # <--- 您提供的路径

# 2. 要标记的城市/地点列表 (使用日文名称)
CITIES_STAYED = [
    "東京", "大阪", "神戸", "札幌", "尾道", "金沢",
    "下田市", "小樽", "知床ウトロ", "横浜", "釧路", "江ノ島",
    "船橋", 
    # "祝津"
]

CITIES_VISITED = [
    "京都", "姫路", "太海", 
    "網走", "紋別市", "知床ウトロ", "斜里", "野付", "阿寒湖", "旭川",
    "伊豆高原", "さいたま市", "豊郷町", "彦根", "大津",
    "奈良", "鎌倉", "岡山",  "中標津空港", "関西空港", "熱川", "新千歳空港",
]

# 3. 地理编码代理设置
HTTP_PROXY = "http://127.0.0.1:7890"
HTTPS_PROXY = "http://127.0.0.1:7890" 

# 4. 日文字体设置
JAPANESE_FONT_NAME = "MS Gothic"

# 5. 位置缓存文件
LOCATION_CACHE_FILE = "locations_cache.json"

# 6. 地图样式参数
BACKGROUND_COLOR = 'white'
MAP_LAND_COLOR = '#f0f0f0'
MAP_OUTLINE_COLOR = '#a0a0a0'
MAP_OUTLINE_LINEWIDTH = 0.6

# 7. "住宿过" (STAYED) 的城市标记样式
STAYED_CITY_MARKER_FACE_COLOR = 'white'
STAYED_CITY_MARKER_EDGE_COLOR = 'black'
STAYED_CITY_MARKER_SIZE = 40
STAYED_CITY_MARKER_LINEWIDTH = 1.0
STAYED_CITY_MARKER_ZORDER = 4

# 8. "住宿过" (STAYED) 的城市标签样式
STAYED_CITY_LABEL_COLOR = 'black'
STAYED_CITY_LABEL_FONTSIZE = 12
STAYED_CITY_LABEL_OUTLINE_COLOR = 'white'
STAYED_CITY_LABEL_OUTLINE_WIDTH = 2.0
STAYED_CITY_LABEL_ZORDER = 5

# 9. "仅旅游过" (VISITED) 的城市标记样式
VISITED_CITY_MARKER_SHAPE = 'o'
VISITED_CITY_MARKER_FACE_COLOR = 'black'
VISITED_CITY_MARKER_EDGE_COLOR = 'black'
VISITED_CITY_MARKER_SIZE = 15
VISITED_CITY_MARKER_LINEWIDTH = 1
VISITED_CITY_MARKER_ZORDER = 4

# 10. "仅旅游过" (VISITED) 的城市标签设置
VISITED_CITY_LABEL_ENABLED = True # 您已启用
VISITED_CITY_LABEL_COLOR = '#333333'
VISITED_CITY_LABEL_FONTSIZE = 10
VISITED_CITY_LABEL_OUTLINE_COLOR = 'white'
VISITED_CITY_LABEL_OUTLINE_WIDTH = 1
VISITED_CITY_LABEL_ZORDER = 5

# 11. 地图显示范围 (经度, 纬度)，用于聚焦日本主要岛屿
# 示例范围 (min_longitude, max_longitude) 和 (min_latitude, max_latitude)
MAP_VIEW_XLIM = (127, 147)  # 经度范围：例如从九州西部到北海道东部
MAP_VIEW_YLIM = (29, 46)    # 纬度范围：例如从九州南部到北海道北部
                            # (这个纬度范围可能不完全包含冲绳县的所有岛屿，请按需调整)
                            # 例如，要包含冲绳本岛 (那霸约 26.2°N)，可将纬度下限调至 26 或更低。
                            # 如果要包含更南的先岛诸岛 (如石垣岛约 24.3°N)，需进一步调低。
                            # 小笠原群岛约在 (142°E, 27°N)，此设定会排除它们。

# 12. 日本都道府县界线数据路径和样式
#     数据来源推荐：
#     - GADM (Level 1 for Japan), e.g., "gadm41_JPN_1.shp"
#     - Natural Earth "Admin 1 – States, Provinces", e.g., "ne_10m_admin_1_states_provinces.shp"
PREFECTURES_SHAPEFILE_PATH = r"ne_10m_admin_1_states_provinces\ne_10m_admin_1_states_provinces.shp" # <--- 修改这里! 例如 gadm41_JPN_1.shp 或 ne_10m_admin_1_states_provinces.shp
PREFECTURES_EDGE_COLOR = '#b0b0b0'  # 都道府县边界线颜色 (比国家轮廓线稍浅或不同)
PREFECTURES_LINEWIDTH = 0.4       # 都道府县边界线线宽
PREFECTURES_ZORDER = 2            # 确保在国家陆地之上，城市标记之下


# --- 缓存文件辅助函数 (无变化) ---
def load_location_cache(cache_file_path):
    if os.path.exists(cache_file_path):
        try:
            with open(cache_file_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                print(f"位置缓存已从 '{cache_file_path}' 加载。")
                return cache_data
        except json.JSONDecodeError:
            print(f"警告: 缓存文件 '{cache_file_path}' 格式错误。将创建新缓存。")
            return {}
        except Exception as e:
            print(f"警告: 读取缓存文件 '{cache_file_path}' 时出错: {e}。将创建新缓存。")
            return {}
    print("未找到缓存文件，将创建新缓存。")
    return {}

def save_location_cache(cache_file_path, cache_data):
    try:
        with open(cache_file_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=4, sort_keys=True)
        print(f"位置缓存已保存到 '{cache_file_path}'")
    except Exception as e:
        print(f"错误: 保存缓存文件 '{cache_file_path}' 时出错: {e}")

# --- 辅助函数：获取字体属性 (无变化) ---
def get_font_properties(font_name_or_path):
    fp = None
    if font_name_or_path:
        try:
            if os.path.exists(font_name_or_path):
                fp = font_manager.FontProperties(fname=font_name_or_path)
            else:
                fp = font_manager.FontProperties(family=font_name_or_path)
            if font_manager.findfont(fp, fallback_to_default=False):
                 print(f"日文字体 '{font_name_or_path}' 已找到并加载。")
            else:
                resolved_font_path = font_manager.findfont(fp, fallback_to_default=True)
                if font_name_or_path.lower() not in resolved_font_path.lower() and \
                   ("fallback" in resolved_font_path.lower() or "default" in resolved_font_path.lower() or "DejaVuSans" in resolved_font_path):
                     print(f"警告: 指定的日文字体 '{font_name_or_path}' 可能未完全匹配，找到了 '{resolved_font_path}'。标签可能无法正确显示日文。")
        except ValueError:
            print(f"警告: 指定的日文字体 '{font_name_or_path}' 未找到。标签可能无法正确显示日文。")
            fp = None
        except Exception as e:
            print(f"加载日文字体 '{font_name_or_path}' 时出错: {e}。将使用默认字体。")
            fp = None
    if not fp:
        print("提示: 如果日文显示为方框，请确保正确安装并配置了 'JAPANESE_FONT_NAME'。")
    return fp
# --- API坐标获取函数 (无变化) ---
def get_city_coordinates_from_api(city_name_japanese):
    proxies = {}
    if HTTP_PROXY: proxies['http'] = HTTP_PROXY
    if HTTPS_PROXY: proxies['https'] = HTTPS_PROXY # Ensure this proxy URL is correct for HTTPS requests
    
    geolocator_user_agent = "japan_map_plotter_v6_proxy" if proxies else "japan_map_plotter_v6_no_proxy"
    
    # Handle empty proxies dict for Nominatim
    current_proxies = proxies if proxies else None

    geolocator = Nominatim(user_agent=geolocator_user_agent, proxies=current_proxies)
    query = f"{city_name_japanese}, 日本"
    print(f"正在通过 API 获取 '{query}' 的坐标...")
    try:
        location = geolocator.geocode(query, timeout=15)
        time.sleep(1.1)
        if location:
            print(f"API 找到 '{city_name_japanese}': ({location.latitude:.4f}, {location.longitude:.4f})")
            return (location.latitude, location.longitude)
        else:
            print(f"API 未能找到 '{city_name_japanese}'。")
            return None
    except Exception as e:
        print(f"API 获取 '{city_name_japanese}' 位置时发生错误: {e}")
        return None

# --- 主要绘图函数 ---
def draw_japan_map_with_cities(shapefile_path, prefectures_gdf, all_cities_gdf, font_prop, output_filename="japan_map_with_cities.png"):
    try:
        world_gdf = geopandas.read_file(shapefile_path)
        japan_gdf = world_gdf[world_gdf['ADMIN'] == 'Japan']
        if japan_gdf.empty:
            print("错误: 未能在国家 Shapefile 中找到 'Japan' 的数据。")
            return

        fig, ax = plt.subplots(1, 1, figsize=(13, 15))
        fig.patch.set_facecolor(BACKGROUND_COLOR)
        ax.set_facecolor(BACKGROUND_COLOR)

        

        # 用于 adjustText 的点列表 (marker的中心)
        points_for_adjusttext = []
        # 用于 adjustText 的文本对象列表
        texts_to_adjust = []

        # 筛选并绘制 "仅旅游过" (VISITED) 的城市标记
        visited_cities_gdf = all_cities_gdf[all_cities_gdf['type'] == 'visited']
        if not visited_cities_gdf.empty:
            visited_cities_gdf.plot(ax=ax, marker=VISITED_CITY_MARKER_SHAPE,
                                    facecolors=VISITED_CITY_MARKER_FACE_COLOR,
                                    edgecolors=VISITED_CITY_MARKER_EDGE_COLOR,
                                    linewidths=VISITED_CITY_MARKER_LINEWIDTH,
                                    markersize=VISITED_CITY_MARKER_SIZE,
                                    zorder=VISITED_CITY_MARKER_ZORDER,
                                    label='旅行した')
            if VISITED_CITY_LABEL_ENABLED:
                for idx, row in visited_cities_gdf.iterrows():
                    points_for_adjusttext.append(row.geometry) # 添加点本身

        # 筛选并绘制 "住宿过" (STAYED) 的城市标记
        stayed_cities_gdf = all_cities_gdf[all_cities_gdf['type'] == 'stayed']
        if not stayed_cities_gdf.empty:
            stayed_cities_gdf.plot(ax=ax, marker='o',
                                   facecolors=STAYED_CITY_MARKER_FACE_COLOR,
                                   edgecolors=STAYED_CITY_MARKER_EDGE_COLOR,
                                   linewidths=STAYED_CITY_MARKER_LINEWIDTH,
                                   markersize=STAYED_CITY_MARKER_SIZE,
                                   zorder=STAYED_CITY_MARKER_ZORDER,
                                   label='滞在した')
            for idx, row in stayed_cities_gdf.iterrows():
                points_for_adjusttext.append(row.geometry) # 添加点本身


        # 添加城市标签 (将文本对象收集到列表中)
        text_path_effects_stayed = [
            path_effects.Stroke(linewidth=STAYED_CITY_LABEL_OUTLINE_WIDTH, foreground=STAYED_CITY_LABEL_OUTLINE_COLOR),
            path_effects.Normal()
        ]
        text_path_effects_visited = [
            path_effects.Stroke(linewidth=VISITED_CITY_LABEL_OUTLINE_WIDTH, foreground=VISITED_CITY_LABEL_OUTLINE_COLOR),
            path_effects.Normal()
        ]

        original_locations = []

        for idx, row in all_cities_gdf.iterrows():
            name = row['name']
            name_display = name.replace("市", "").replace("町", "").replace("村", "")
            
            # 初始偏移量 (dx, dy) - adjustText 会以此为起点进行调整
            # 这些可以设为较小的值，或根据经验初步设定
            dx, dy = 0, 0 # 统一的较小初始偏移
            
            # # (可选) 您仍然可以保留一些非常特定的初始偏移，如果需要的话
            if name == "関西空港": dx = 0.2; dy = -0.5
            elif name == "神戸": dx = -0.7; dy = -0.5
            elif name == "京都": dx = -0.3; dy = 0.5
            elif name == "横浜": dx = -0.3; dy = 0
            elif name == "下田市": dx = -0.5; dy = -0.7
            elif name in ["中標津空港", "野付", "釧路"]: dx = 0; dy = -0.7

            original_locations.append(row.geometry) # 记录原始位置

            text_obj = None
            if row['type'] == 'stayed':
                text_obj = ax.text(row.geometry.x + dx, row.geometry.y + dy, name_display,
                                   fontsize=STAYED_CITY_LABEL_FONTSIZE,
                                   color=STAYED_CITY_LABEL_COLOR,
                                   fontproperties=font_prop,
                                   path_effects=text_path_effects_stayed,
                                   ha='left', va='bottom',
                                   zorder=STAYED_CITY_LABEL_ZORDER)
            elif row['type'] == 'visited' and VISITED_CITY_LABEL_ENABLED:
                text_obj = ax.text(row.geometry.x + dx, row.geometry.y + dy, name_display, # 使用相同的初始dx,dy
                                   fontsize=VISITED_CITY_LABEL_FONTSIZE,
                                   color=VISITED_CITY_LABEL_COLOR,
                                   fontproperties=font_prop,
                                   path_effects=text_path_effects_visited,
                                   ha='left', va='bottom',
                                   zorder=STAYED_CITY_LABEL_ZORDER)
            if text_obj:
                texts_to_adjust.append(text_obj)
        
        # 调用 adjust_text 进行标签调整
        if texts_to_adjust:
            print(f"正在使用 adjustText 调整 {len(texts_to_adjust)} 个标签位置以减少重叠...")
            # adjust_text 需要 x, y 坐标作为参考点，但我们已经把Text对象初步放置了。
            # 它会尝试调整这些Text对象。
            # 如果标签与点（marker）重叠，可以传递点的坐标给 `add_objects` 或通过 `x`, `y` 参数（如果Text对象没有预先放置）
            # 这里，我们让它调整已有的Text对象，并可以告诉它哪些点是它们不应覆盖的。
            # `points_for_adjusttext` 包含所有标记的 GeoPandas Point 对象
            
            # 从GeoPandas Point对象中提取x, y坐标列表
            x_points = [p.x for p in points_for_adjusttext]
            y_points = [p.y for p in points_for_adjusttext]

            target_x = [p.x for p in original_locations]
            target_y = [p.y for p in original_locations]

            adjust_text(texts_to_adjust,
                        x=x_points, # 提供原始点坐标，帮助 adjustText 避免覆盖点
                        y=y_points,
                        target_x=target_x,
                        target_y=target_y,
                        objects=ax.collections, # 考虑已绘制的散点图集合 (ax.collections包含plot()产生的PathCollection)
                        expand=(1.3, 1.3),
                        pull_threshold=10,
                        only_move={"text": "xy", "static": "xy", "explode": "xy", "pull": "xy"},
                        force_static=5,         # 点对文本的排斥力
                        force_text=5,            # 文本之间的排斥力
                        force_pull=0.00 ,
                        force_explode=0,
                        iter_lim=5000,                   # 最大迭代次数
                        arrowprops=dict(arrowstyle="-", color='grey', lw=1, alpha=1, zorder=3.5) # 可选：箭头
                       )
            print("adjustText 完成。")

        # 1. 绘制日本国家轮廓 (zorder=1)
        japan_gdf.plot(ax=ax, edgecolor=MAP_OUTLINE_COLOR, facecolor=MAP_LAND_COLOR,
                       linewidth=MAP_OUTLINE_LINEWIDTH, zorder=1)

        # 2. 绘制都道府县边界 (zorder=2)
        if prefectures_gdf is not None and not prefectures_gdf.empty:
            print(f"正在绘制 {len(prefectures_gdf)} 个都道府县的边界...")
            prefectures_gdf.plot(ax=ax,
                                 edgecolor=PREFECTURES_EDGE_COLOR,
                                 facecolor='none', # 通常不填充内部边界的颜色
                                 linewidth=PREFECTURES_LINEWIDTH,
                                 zorder=PREFECTURES_ZORDER)
        elif prefectures_gdf is None:
            print("提示: 未提供都道府县数据文件路径，将跳过绘制都道府县边界。")
        else: # empty GeoDataFrame
            print("警告: 都道府县数据为空，无法绘制边界。")

        ax.set_xticks([])
        ax.set_yticks([])
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.spines['left'].set_visible(False)

        minx, miny, maxx, maxy = japan_gdf.total_bounds
        ax.set_xlim(MAP_VIEW_XLIM)
        ax.set_ylim(MAP_VIEW_YLIM)

        handles, labels = ax.get_legend_handles_labels()
        if handles: # 只有当有label的plot元素时才显示图例
             ax.legend(handles, labels,
                       loc='lower right',               # 将图例的“右下角”作为锚点
                       bbox_to_anchor=(0.75, 0.2),     # 将此锚点放置在坐标轴的 (x=97%, y=3%) 位置
                                                       # (0,0)是轴的左下角, (1,1)是轴的右上角
                                                       # 您可以调整 (0.97, 0.03) 这两个值，
                                                       # 例如 (0.95, 0.05) 会更靠内一些
                       fontsize='large',               # 将字体调大
                       frameon=True,                   # 保持无边框
                       prop=font_prop,                  # 继续使用指定的日文字体属性
                       markerscale=1.5,                 # 将图例中的标记放大1.5倍
                       labelspacing=0.8,                # 调整条目间的垂直间距 (可选)
                       handletextpad=0.5,               # 调整标记和文本的间距 (可选)
                    #    title='图例',                    # 可选：为图例添加标题
                    #    title_fontproperties=font_prop   # 图例标题也使用同样的字体属性
                      )

        plt.tight_layout(pad=0.5)
        plt.savefig(output_filename, dpi=500, facecolor=fig.get_facecolor())
        print(f"地图已保存为: {output_filename}")
        # plt.show()

    except FileNotFoundError:
        print(f"错误: Shapefile 未找到于路径 '{shapefile_path}'。")
    except Exception as e:
        print(f"绘制地图时发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if SHAPEFILE_PATH == "path/to/your/ne_50m_admin_0_countries.shp": # 检查默认占位符
        print("请先修改脚本顶部的 'SHAPEFILE_PATH' 变量。")
    elif not JAPANESE_FONT_NAME:
        print("请在脚本顶部配置 'JAPANESE_FONT_NAME' 以正确显示日文标签。")
    else:
        font_properties = get_font_properties(JAPANESE_FONT_NAME)
        location_cache = load_location_cache(LOCATION_CACHE_FILE)
        cache_updated = False

        # 新增：加载都道府县数据
        japan_prefectures_gdf = None
        if PREFECTURES_SHAPEFILE_PATH and PREFECTURES_SHAPEFILE_PATH != r"path\to\your\japan_prefectures.shp":
            try:
                print(f"正在加载都道府县数据从: {PREFECTURES_SHAPEFILE_PATH}")
                all_admin1_gdf = geopandas.read_file(PREFECTURES_SHAPEFILE_PATH)
                
                # 如果使用的是 Natural Earth 的全球 Admin 1 文件，需要筛选出日本的都道府县
                # Natural Earth 的 'ne_10m_admin_1_states_provinces.shp' 文件中
                # 通常有 'adm0_a3' (ISO 3166-1 alpha-3 国家代码) 或 'admin' (国家名) 列
                # 请根据您下载的文件的实际列名进行调整
                # 例如，检查: print(all_admin1_gdf.columns)
                # 然后取消注释并修改下面的行
                if 'adm0_a3' in all_admin1_gdf.columns: # 适用于 Natural Earth
                    japan_prefectures_gdf = all_admin1_gdf[all_admin1_gdf['adm0_a3'] == 'JPN']
                elif 'SOV_A3' in all_admin1_gdf.columns and 'ADMIN' in all_admin1_gdf.columns: # 另一种 Natural Earth 可能的列组合
                     japan_prefectures_gdf = all_admin1_gdf[all_admin1_gdf['SOV_A3'] == 'JPN'] # 或者 ADMIN == 'Japan'
                # 如果您下载的是 GADM 提供的日本专用 Level 1 文件 (如 gadm41_JPN_1.shp)
                # 则该文件本身就只包含日本的都道府县，无需此处的筛选步骤
                #可以直接 japan_prefectures_gdf = all_admin1_gdf
                else: # 假设是日本专用文件，或需要用户确认如何筛选
                    print("警告: 未能自动从都道府县文件中筛选日本数据。如果这是全球数据，请修改脚本中的筛选逻辑。如果这是日本专用数据，此警告可忽略。")
                    japan_prefectures_gdf = all_admin1_gdf # 直接使用，假设是日本专用

                if japan_prefectures_gdf.empty:
                    print(f"警告: 从 '{PREFECTURES_SHAPEFILE_PATH}' 中未能筛选出日本的都道府县数据。")
                    japan_prefectures_gdf = None #确保设置为空，如果筛选失败

            except Exception as e:
                print(f"错误: 加载或处理都道府县数据 '{PREFECTURES_SHAPEFILE_PATH}' 时失败: {e}")
                japan_prefectures_gdf = None
        else:
            print("提示: 未配置有效的都道府县数据文件路径 ('PREFECTURES_SHAPEFILE_PATH')。")

        
        all_cities_data_list = []
        processed_names = set()

        # 1. 处理住宿过的城市
        for city_name in CITIES_STAYED:
            if city_name in processed_names: continue
            coords = None
            if city_name in location_cache:
                print(f"从缓存加载 '{city_name}' (住宿)。")
                coords = (location_cache[city_name]['latitude'], location_cache[city_name]['longitude'])
            else:
                coords = get_city_coordinates_from_api(city_name)
                if coords:
                    location_cache[city_name] = {'latitude': coords[0], 'longitude': coords[1]}
                    cache_updated = True
            
            if coords:
                all_cities_data_list.append({'name': city_name, 'latitude': coords[0], 'longitude': coords[1], 'type': 'stayed'})
                processed_names.add(city_name)
            else:
                print(f"无法获取 '{city_name}' (住宿) 的坐标。")

        # 2. 处理仅旅游过的城市
        for city_name in CITIES_VISITED:
            if city_name in processed_names:
                print(f"'{city_name}' 已作为住宿地处理，跳过旅游地标记。")
                continue
            coords = None
            if city_name in location_cache:
                print(f"从缓存加载 '{city_name}' (旅游)。")
                coords = (location_cache[city_name]['latitude'], location_cache[city_name]['longitude'])
            else:
                coords = get_city_coordinates_from_api(city_name)
                if coords:
                    location_cache[city_name] = {'latitude': coords[0], 'longitude': coords[1]}
                    cache_updated = True

            if coords:
                all_cities_data_list.append({'name': city_name, 'latitude': coords[0], 'longitude': coords[1], 'type': 'visited'})
                processed_names.add(city_name)
            else:
                print(f"无法获取 '{city_name}' (旅游) 的坐标。")

        if cache_updated:
            save_location_cache(LOCATION_CACHE_FILE, location_cache)

        if not all_cities_data_list:
            print("未能获取任何有效的城市坐标，无法继续绘图。")
        else:
            all_cities_gdf = pd.DataFrame(all_cities_data_list)
            geometry = [Point(xy) for xy in zip(all_cities_gdf['longitude'], all_cities_gdf['latitude'])]
            all_cities_gdf = geopandas.GeoDataFrame(all_cities_gdf, geometry=geometry, crs="EPSG:4326")

            print("\n最终用于绘图的城市数据:")
            print(all_cities_gdf[['name', 'type', 'latitude', 'longitude']])
            draw_japan_map_with_cities(SHAPEFILE_PATH, japan_prefectures_gdf, all_cities_gdf, font_properties)