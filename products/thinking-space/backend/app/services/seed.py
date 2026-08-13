from app.models import Dimension, Layer

V1_LAYERS = [
    (0, "细胞", "生命的基本单位，分子层面的运作"),
    (1, "组织", "细胞群落的协同与分化"),
    (2, "器官", "功能特化的结构单元"),
    (3, "系统", "多器官协调的生理网络"),
    (4, "人", "个体层面的意识、行为、健康"),
    (5, "社会", "人际关系、文化、群体动态"),
    (6, "国家", "治理、制度、经济、法律"),
    (7, "世界", "全球互联、地缘、环境"),
    (8, "星系", "天体物理、宇宙结构"),
    (9, "宇宙", "起源、法则、存在本身"),
]

def seed_v1_data(db):
    existing = db.query(Dimension).filter(Dimension.name == "物质层次").first()
    if existing:
        return existing

    dim = Dimension(name="物质层次", description="从物理本质出发的层级分解", sort_order=0)
    db.add(dim)
    db.flush()

    for level, name, desc in V1_LAYERS:
        layer = Layer(dimension_id=dim.id, name=name, level=level, description=desc, sort_order=level)
        db.add(layer)

    db.commit()
    return dim
