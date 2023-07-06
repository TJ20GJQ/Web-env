from flask import Flask  # 导入Flask模块
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

app = Flask(__name__, static_url_path='/s', static_folder='static', template_folder='templates')

HOSTNAME = "127.0.0.1"  # MySQL所在主机名
PORT = 3306  # MySQL监听的端口号，默认3306
USERNAME = "root"  # 连接MySQL的用户名，自己设置
PASSWORD = "GJQ123"  # 连接MySQL的密码，自己设置
DATABASE = "flask_test"  # MySQL上创建的数据库名称
# 通过修改以下代码来操作不同的SQL比写原生SQL简单很多 --》通过ORM可以实现从底层更改使用的SQL
app.config[
    'SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{USERNAME}:{PASSWORD}@{HOSTNAME}:{PORT}/{DATABASE}?charset=utf8mb4"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = True

db = SQLAlchemy(app)


class BaseModel(db.Model):
    __abstract__ = True  # 抽象类，可以将其他数据表中的公共字段存放在这个类中，然后继承该类
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)


Article_Tag = db.Table(
    "acticle_tag",
    db.Column("id", db.Integer, primary_key=True, autoincrement=True),
    db.Column("article_id", db.Integer, db.ForeignKey("article.id")),
    db.Column("tag_id", db.Integer, db.ForeignKey("tag.id"))
)  # 创建多对多表


class Article(BaseModel):
    __tablename__ = "article"
    title = db.Column(db.String(20))
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    tag = db.relationship(
        "Tag",  # 定义关联的数据表，正向查询时使用“tag”进行查询
        secondary=Article_Tag,  # 多对多关系中关联的中间表
        lazy="dynamic",  # 指定sqlalchemy数据库何时加载数据
        backref=db.backref("article", lazy="dynamic")  # 指定反向查询时使用的名称和何时加载数据
    )


class Tag(BaseModel):
    __tablename__ = "tag"
    name = db.Column(db.String(20))


class User(BaseModel):
    __tablename__ = "user"
    username = db.Column(db.String(10))
    phone = db.Column(db.String(11))
    article = db.relationship(
        "Article",
        backref="Author"
    )


with app.app_context():
    db.create_all()  # 在数据库中生成数据表


# db.drop_all() 删除数据库中的数据表


def query2dict(model_list):
    if isinstance(model_list, list):  # 如果传入的参数是一个list类型的，说明是使用的all()的方式查询的
        if isinstance(model_list[0], db.Model):  # 这种方式是获得的整个对象  相当于 select * from table
            lst = []
            for model in model_list:
                dic = {}
                for col in model.__table__.columns:
                    dic[col.name] = getattr(model, col.name)
                lst.append(dic)
            return lst
        else:  # 这种方式获得了数据库中的个别字段  相当于select id,name from table
            lst = []
            for result in model_list:  # 当以这种方式返回的时候，result中会有一个keys()的属性
                lst.append([dict(zip(result.keys, r)) for r in result])
            return lst
    else:  # 不是list,说明是用的get() 或者 first()查询的，得到的结果是一个对象
        if isinstance(model_list, db.Model):  # 这种方式是获得的整个对象  相当于 select * from table limit=1
            dic = {}
            for col in model_list.__table__.columns:
                dic[col.name] = getattr(model_list, col.name)
            return dic
        else:  # 这种方式获得了数据库中的个别字段  相当于select id,name from table limit = 1
            return dict(zip(model_list.keys(), model_list))


@app.route('/')
def hello_world():
    # with db.engine.connect() as conn:
    #     rs = conn.execute(text("select * from a"))
    #     print(rs.fetchall())
    #     return 'Hello World!' + str(rs.fetchall())
    addme = User()
    addyou = User(phone='15646516565', username='abcd')
    addme.phone = '15900251069'
    addme.username = 'iguo'
    db.session.add(addme)
    db.session.add(addyou)
    db.session.commit()
    print(User.query.all()[0].__table__.columns)
    # return query2dict(User.query.filter_by(username='iguo').first())
    return query2dict(User.query.all())


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=False)
