
from concurrent.futures import ThreadPoolExecutor
import datetime as dt  # 將 datetime 模組重新命名為 'dt' 來避免衝突
from flask import Flask,render_template,url_for,redirect,request, flash,session,g
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import pymongo
import json
from google.oauth2 import id_token
from google.auth.transport import requests
from flask import jsonify
import pymysql
from authlib.integrations.flask_client import OAuth
from search_news import *
from word2vec import *

myclient = pymongo.MongoClient("mongodb+srv://user1:user1@cluster0.ronm576.mongodb.net/?retryWrites=true&w=majority")
# 建立資料庫連接
def connect_db():
    db_settings = {
            "host": "127.0.0.1",
            "port": 3306,
            "user": "root",
            "password": "109403502",
            "db": "communews",
            "charset": "utf8mb4",
            "cursorclass": pymysql.cursors.DictCursor
        }
    connection = pymysql.connect(**db_settings)
    return connection   
def news_score_loader(user_id,news_id):  
    db = connect_db()
    cursor = db.cursor()
    query = "SELECT * FROM tb_news_score WHERE id_user = %s AND id_news= %s"
    cursor.execute(query, (user_id,news_id))
    result = cursor.fetchone()
    if result:
        have ='Y'
        score =result ['score']
        return have,score
    else:
        have ='N'
        score = 0
        return have,score
def kw_loader(kw):  
    db = connect_db()
    cursor = db.cursor()
    query = "SELECT * FROM tb_keyword WHERE value = %s"
    cursor.execute(query, kw)
    result = cursor.fetchone()
    if result:
        kw_id = result['id_keyword']
        return kw_id
    else:
        sql_insert = "INSERT INTO tb_keyword (value) VALUES (%s)"
        data = (kw)
        cursor.execute(sql_insert, data)
        # 提交變更
        db.commit()
        return kw_loader(kw) 
def collection_loader(kw):  
    id_keyword=kw_loader(kw)
    db = connect_db()
    cursor = db.cursor()
    query = "SELECT * FROM tb_collection_record WHERE id_keyword = %s AND id_user=%s"
    cursor.execute(query, (id_keyword,current_user.user_id))
    result = cursor.fetchone()
    if result:
        have = 'Y'
        ISLIKE = result['islike']
        return ISLIKE,have
    else:
        have = 'N'
        ISLIKE = 'N'
        return ISLIKE,have
def user_collection_loader():
    db = connect_db()
    cursor = db.cursor()
    query1 = "SELECT * FROM tb_collection_record WHERE id_user=%s"
    cursor.execute(query1, (current_user.user_id))
    results1 = cursor.fetchall()  # 獲取所有結果

    collection_kw_nm = []  # 用於存儲收藏的關鍵字ID

    for index, result in enumerate(results1, start=1):
        kw_id = result['id_keyword']
        query2 = "SELECT * FROM tb_keyword WHERE id_keyword=%s"
        cursor.execute(query2, (kw_id))
        results2 = cursor.fetchone()  
        keyword = results2['value']
        collection_kw_nm.append((index, keyword))

    return collection_kw_nm
def do_like(request):
    db = connect_db()
    cursor = db.cursor()
    data = request.json
    data_id = data.get('data_id')
    ISLIKE = data.get('like_status')
    if ISLIKE == 'Y' :
        if collection_loader(data_id)[1] =="Y":
            sql_insert = "UPDATE tb_collection_record SET islike =%s ,date=%s WHERE id_user = %s AND id_keyword=%s "
            data = (ISLIKE,(dt.date.today().strftime("%Y-%m-%d")),current_user.user_id, kw_loader(data_id))
        else:
            sql_insert = "INSERT INTO tb_collection_record (id_user,id_keyword,islike,rating,date) VALUES (%s,%s,%s,%s,%s)"
            data = (current_user.user_id, kw_loader(data_id), ISLIKE, 5, (dt.date.today().strftime("%Y-%m-%d")))

        cursor.execute(sql_insert, data)
        # 提交變更
        db.commit()
    elif ISLIKE == 'N' :
        sql_insert = "UPDATE tb_collection_record SET islike =%s ,date=%s WHERE id_user = %s AND id_keyword=%s "
        data = (ISLIKE,(dt.date.today().strftime("%Y-%m-%d")),current_user.user_id, kw_loader(data_id))
        cursor.execute(sql_insert, data)
        # 提交變更
        db.commit()
        
def do_rating(request):
    db = connect_db()
    cursor = db.cursor()
    data = request.json
    news_id = data.get('news_id')
    news_topic = data.get('topic')
    rating = data.get('rating')
    have,score=news_score_loader(current_user.user_id,news_id)
    #如果存在 就改分數
    if have =='Y':
        sql_insert = "UPDATE tb_news_score SET score=%s WHERE id_user =%s AND id_news=%s "
        data = (rating,current_user.user_id,news_id)
        cursor.execute(sql_insert, data)
        # 提交變更
        db.commit()
    #如果不存在 就加入資料
    elif have=='N':
        sql_insert = "INSERT INTO tb_news_score (id_user,id_news,news_topic,score) VALUES (%s,%s,%s,%s)"
        data = (current_user.user_id,news_id,news_topic,rating)
        cursor.execute(sql_insert, data)
        # 提交變更
        db.commit()
    
app = Flask( 
    __name__,
    static_folder='static',
    static_url_path='/'
)
#  會使用到session，故為必設
app.secret_key = 'NCUMIS' 
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self,user_id, email, password):
        self.user_id = user_id
        self.email = email
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_id(self):
        return self.user_id

@app.before_request
def before_request():
    g.user = current_user

@login_manager.user_loader  
def user_loader(user_id):  
    db = connect_db()
    cursor = db.cursor()
    query = "SELECT * FROM tb_user WHERE id_user = %s"
    cursor.execute(query, (user_id))
    result = cursor.fetchone()
    if result:
        user_id = result['id_user']
        email = result['email']
        password = result['password']
        user = User(user_id,email, password)
        return user
    return None

@app.route("/login",methods=['GET','POST'])
def login():
    db = connect_db()
    if request.method == 'POST':
        # 获取表单数据
        input_email = request.form['email']
        input_password = request.form['password']

        # 查询数据库以获取用户
        cursor = db.cursor()
        query = "SELECT * FROM tb_user WHERE email = %s"
        cursor.execute(query, (input_email))
        result = cursor.fetchone()

        # 验证邮箱和密码
        if result and check_password_hash(result['password'], input_password):
            # 构造 User 对象
            user = User(result['id_user'],result['email'], result['password'])
            login_user(user)  # 登录用户
            flash('Login success.')
            return redirect(url_for('index'))  # 重定向到主页
        else:
            flash('Invalid email or password.')  # 如果验证失败，显示错误消息
            return redirect(url_for('login'))  # 重定向回登录页

    return render_template('login.html')


@app.route("/register",methods=['GET','POST'])
def register():
    db = connect_db()
    if request.method == 'POST':
        # 获取表单数据
        input_email = request.form['email']
        input_password = request.form['password']
        input_repeat_password = request.form['password-repeat']

        # 验证输入
        if input_password != input_repeat_password:
            flash('Two passwords are different.')
            return redirect(url_for('register'))

        # 检查是否已注册
        cursor = db.cursor()
        query = "SELECT * FROM tb_user WHERE email = %s"
        cursor.execute(query, (input_email,))
        result = cursor.fetchone()
        if result:
            flash('Email has already been registered.')
            return redirect(url_for('register'))

        # 生成密码哈希值
        password_hash = generate_password_hash(input_password)

        # 执行插入操作
        query = "INSERT INTO tb_user (email, password) VALUES (%s, %s)"
        cursor.execute(query, (input_email, password_hash))
        db.commit()

        flash("Thank you for registering.")
        return redirect(url_for('login'))

    return render_template('register.html')


# 建立網站首頁的回應方式
@app.route("/", methods=['GET','POST'])
def index():
    if request.method == 'GET':
        ######要把資料庫有紀錄的評分放上去
        topics=["運動","生活","國際","娛樂","社會地方","科技","健康","財經"]
        combined_data = []
        # 使用线程池并行处理获取数据
        with ThreadPoolExecutor() as executor:
            # 并行获取各个主题的数据
            futures = [executor.submit(get_DB_News_data, topic,50) for topic in topics]
            # 收集各个主题的数据
            for future in futures:
                combined_data.extend(future.result())
        # 按照timestamp字段排序
        sorted_data = sorted(combined_data, key=lambda x: x['timestamp'], reverse=True)
        # 取得當前用戶ID
        current_user_id = g.user.user_id if g.user.is_authenticated else None
        # 逐一查詢每筆新聞的評分分數，並加回到sorted_data中
        for news in sorted_data:
            if current_user_id:
                # 從資料庫查詢用戶之前對該新聞的評分
                have, score = news_score_loader(current_user_id, news['_id'])
                if have == 'Y':
                    # 如果用戶之前有評分，將評分分數加回到sorted_data中
                    news['rating'] = score
                else:
                    # 如果用戶之前沒有評分，設置評分為0
                    news['rating'] = 0
            else:
                # 如果用戶未登入，設置評分為0
                news['rating'] = 0
        return render_template('newest.html', news_list=sorted_data,user=g.user)
    elif request.method == 'POST':
        if g.user.is_authenticated:
            data = request.json
            action = data.get('action')
            if action =='rating':
                do_rating(request)
                return jsonify({'message': "評分成功"})
        else:
            print("這邊還沒做 html要多加彈跳提醒登入方塊")
            return "這邊還沒做 html要多加彈跳提醒登入方塊"



@app.route("/hot", methods=['GET','POST'])
def hot():
    like_status_dict={}
    stars_count_dict = {}  # 用於存儲每個新聞的星星數量
    if request.method == 'GET':
        if g.user.is_authenticated:
            data =hot_all_search_news("daily")
            like_status_dict = {keyword: collection_loader(keyword)[0] for keyword in data.keys()}
            # 計算每個新聞的星星數量
            for keyword in data.keys():
                news_id = data[keyword][0]['_id']
                have, score = news_score_loader(g.user.user_id, news_id)
                if have == 'Y':
                    stars_count_dict[news_id] = score
                else:
                    stars_count_dict[news_id] = 0
            return render_template('hot.html', data=data,like_status_dict=like_status_dict,stars_count_dict=stars_count_dict,user=g.user)
        else:
            data =hot_all_search_news("daily")
            return render_template('hot.html', data=data,like_status_dict=like_status_dict,stars_count_dict=stars_count_dict,user=g.user)
    elif request.method == 'POST':
        if g.user.is_authenticated:
            data = request.json
            action = data.get('action')
            if action=='like':
                do_like(request)
                # 回傳JSON格式的回應給前端
                return jsonify({'message': '收藏成功！'})
            elif action =='rating':
                do_rating(request)
                return jsonify({'message': "評分成功"})
        else:
            print("這邊還沒做 html要多加彈跳提醒登入方塊")
            return "這邊還沒做 html要多加彈跳提醒登入方塊"
    else:
        # 在其他情況下也要處理返回有效的回應
        return "Invalid request method"

# 熱門頁面-每週
@app.route("/hot/當週熱門", methods=['GET','POST'])
def everyweek():
    like_status_dict={}
    stars_count_dict = {}  # 用於存儲每個新聞的星星數量
    if request.method == 'GET':
        if g.user.is_authenticated:
            data =hot_all_search_news("weekly")
            like_status_dict = {keyword: collection_loader(keyword)[0] for keyword in data.keys()}
            # 計算每個新聞的星星數量
            for keyword in data.keys():
                news_id = data[keyword][0]['_id']
                have, score = news_score_loader(g.user.user_id, news_id)
                if have == 'Y':
                    stars_count_dict[news_id] = score
                else:
                    stars_count_dict[news_id] = 0
            return render_template('hot_everyweek.html', data=data,like_status_dict=like_status_dict,stars_count_dict=stars_count_dict,user=g.user)
        else:
            data =hot_all_search_news("weekly")
            return render_template('hot_everyweek.html', data=data,like_status_dict=like_status_dict,stars_count_dict=stars_count_dict,user=g.user)
    elif request.method == 'POST':
        if g.user.is_authenticated:
            data = request.json
            action = data.get('action')
            if action=='like':
                do_like(request)
                # 回傳JSON格式的回應給前端
                return jsonify({'message': '收藏成功！'})
            elif action =='rating':
                do_rating(request)
                return jsonify({'message': "評分成功"})
        else:
            print("這邊還沒做 html要多加彈跳提醒登入方塊")
            return "這邊還沒做 html要多加彈跳提醒登入方塊"
    else:
        # 在其他情況下也要處理返回有效的回應
        return "Invalid request method"

# 熱門頁面-每月
@app.route("/hot/當月熱門", methods=['GET','POST'])
def everymonth():
    like_status_dict={}
    stars_count_dict = {}  # 用於存儲每個新聞的星星數量
    if request.method == 'GET':
        if g.user.is_authenticated:
            data =hot_all_search_news("monthly")
            like_status_dict = {keyword: collection_loader(keyword)[0] for keyword in data.keys()}
            # 計算每個新聞的星星數量
            for keyword in data.keys():
                news_id = data[keyword][0]['_id']
                have, score = news_score_loader(g.user.user_id, news_id)
                if have == 'Y':
                    stars_count_dict[news_id] = score
                else:
                    stars_count_dict[news_id] = 0
            return render_template('hot_everymonth.html', data=data,like_status_dict=like_status_dict,stars_count_dict=stars_count_dict,user=g.user)
        else:
            data =hot_all_search_news("monthly")
            return render_template('hot_everymonth.html', data=data,like_status_dict=like_status_dict,stars_count_dict=stars_count_dict,user=g.user)
    elif request.method == 'POST':
        if g.user.is_authenticated:
            data = request.json
            action = data.get('action')
            if action=='like':
                do_like(request)
                # 回傳JSON格式的回應給前端
                return jsonify({'message': '收藏成功！'})
            elif action =='rating':
                do_rating(request)
                return jsonify({'message': "評分成功"})
        else:
            print("這邊還沒做 html要多加彈跳提醒登入方塊")
            return "這邊還沒做 html要多加彈跳提醒登入方塊"
    else:
        # 在其他情況下也要處理返回有效的回應
        return "Invalid request method"


@app.route("/show",  methods=['POST'])
def show():
    if request.method == 'POST':
        combined_data = {}
        keyword = request.form.get("keyword", "")
        data =kw_search_news(keyword)
        combined_data.update(data)
        extend_keywords=word2vec(keyword)
        if extend_keywords!="None":
            for extend_keyword in extend_keywords:
                extend_data=kw_search_news(extend_keyword)
                combined_data.update(extend_data)
        return render_template('show.html',combined_data=combined_data,user=g.user)
    
    return redirect(url_for('index'))  


# topic頁面預設是最新新聞
@app.route("/topic/<topicname>", methods=['GET','POST'])
def topic(topicname):
    if request.method == 'GET':
        news_list=get_DB_News_data(topicname,100)
        # 取得當前用戶ID
        current_user_id = g.user.user_id if g.user.is_authenticated else None
        # 逐一查詢每筆新聞的評分分數，並加回到sorted_data中
        for news in news_list:
            if current_user_id:
                # 從資料庫查詢用戶之前對該新聞的評分
                have, score = news_score_loader(current_user_id, news['_id'])
                if have == 'Y':
                    # 如果用戶之前有評分，將評分分數加回到sorted_data中
                    news['rating'] = score
                else:
                    # 如果用戶之前沒有評分，設置評分為0
                    news['rating'] = 0
            else:
                # 如果用戶未登入，設置評分為0
                news['rating'] = 0
        return render_template('topic.html',topicname=topicname,news_list=news_list,user=g.user)
    elif request.method == 'POST':
        if g.user.is_authenticated:
            data = request.json
            action = data.get('action')
            if action =='rating':
                do_rating(request)
                return jsonify({'message': "評分成功"})
        else:
            print("這邊還沒做 html要多加彈跳提醒登入方塊")
            return "這邊還沒做 html要多加彈跳提醒登入方塊"

# topic的熱門新聞頁面
@app.route("/topic/<topicname>/熱門", methods=['GET','POST'])
def topicHot(topicname):
    like_status_dict={}
    stars_count_dict = {}  # 用於存儲每個新聞的星星數量
    if request.method == 'GET':
        if g.user.is_authenticated:
            data=hot_topic_search_news(topicname,'daily')
            like_status_dict = {keyword: collection_loader(keyword)[0] for keyword in data.keys()}
            # 計算每個新聞的星星數量
            for keyword in data.keys():
                news_id = data[keyword][0]['_id']
                have, score = news_score_loader(g.user.user_id, news_id)
                if have == 'Y':
                    stars_count_dict[news_id] = score
                else:
                    stars_count_dict[news_id] = 0
            return render_template('topic_hot.html',topicname=topicname, data=data,like_status_dict=like_status_dict,stars_count_dict=stars_count_dict,user=g.user)
        else:
            data=hot_topic_search_news(topicname,'daily')
            return render_template('topic_hot.html',topicname=topicname, data=data,like_status_dict=like_status_dict,stars_count_dict=stars_count_dict,user=g.user)
    elif request.method == 'POST':
        if g.user.is_authenticated:
            data = request.json
            action = data.get('action')
            if action=='like':
                do_like(request)
                # 回傳JSON格式的回應給前端
                return jsonify({'message': '收藏成功！'})
            elif action =='rating':
                do_rating(request)
                return jsonify({'message': "評分成功"})
        else:
            print("這邊還沒做 html要多加彈跳提醒登入方塊")
            return "這邊還沒做 html要多加彈跳提醒登入方塊"
    else:
        # 在其他情況下也要處理返回有效的回應
        return "Invalid request method"

@app.route("/topic/<topicname>/熱門/當週", methods=['GET','POST'])
def topic_hot_week(topicname):
    like_status_dict={}
    stars_count_dict = {}  # 用於存儲每個新聞的星星數量
    if request.method == 'GET':
        if g.user.is_authenticated:
            data=hot_topic_search_news(topicname,'weekly')
            like_status_dict = {keyword: collection_loader(keyword)[0] for keyword in data.keys()}
            # 計算每個新聞的星星數量
            for keyword in data.keys():
                news_id = data[keyword][0]['_id']
                have, score = news_score_loader(g.user.user_id, news_id)
                if have == 'Y':
                    stars_count_dict[news_id] = score
                else:
                    stars_count_dict[news_id] = 0
            return render_template('topic_hot_week.html',topicname=topicname, data=data,like_status_dict=like_status_dict,stars_count_dict=stars_count_dict,user=g.user)
        else:
            data=hot_topic_search_news(topicname,'weekly')
            return render_template('topic_hot_week.html',topicname=topicname, data=data,like_status_dict=like_status_dict,stars_count_dict=stars_count_dict,user=g.user)
    elif request.method == 'POST':
        if g.user.is_authenticated:
            data = request.json
            action = data.get('action')
            if action=='like':
                do_like(request)
                # 回傳JSON格式的回應給前端
                return jsonify({'message': '收藏成功！'})
            elif action =='rating':
                do_rating(request)
                return jsonify({'message': "評分成功"})
        else:
            print("這邊還沒做 html要多加彈跳提醒登入方塊")
            return "這邊還沒做 html要多加彈跳提醒登入方塊"
    else:
        # 在其他情況下也要處理返回有效的回應
        return "Invalid request method"

@app.route("/topic/<topicname>/熱門/當月", methods=['GET','POST'])
def topic_hot_month(topicname):
    like_status_dict={}
    stars_count_dict = {}  # 用於存儲每個新聞的星星數量
    if request.method == 'GET':
        if g.user.is_authenticated:
            data=hot_topic_search_news(topicname,'monthly')
            like_status_dict = {keyword: collection_loader(keyword)[0] for keyword in data.keys()}
            #計算每個新聞的星星數量
            for keyword in data.keys():
                news_id = data[keyword][0]['_id']
                have, score = news_score_loader(g.user.user_id, news_id)
                if have == 'Y':
                    stars_count_dict[news_id] = score
                else:
                    stars_count_dict[news_id] = 0
            return render_template('topic_hot_month.html',topicname=topicname, data=data,like_status_dict=like_status_dict,stars_count_dict=stars_count_dict,user=g.user)
        else:
            data=hot_topic_search_news(topicname,'monthly')
            return render_template('topic_hot_month.html',topicname=topicname, data=data,like_status_dict=like_status_dict,stars_count_dict=stars_count_dict,user=g.user)
    elif request.method == 'POST':
        if g.user.is_authenticated:
            data = request.json
            action = data.get('action')
            if action=='like':
                do_like(request)
                # 回傳JSON格式的回應給前端
                return jsonify({'message': '收藏成功！'})
            elif action =='rating':
                do_rating(request)
                return jsonify({'message': "評分成功"})
        else:
            print("這邊還沒做 html要多加彈跳提醒登入方塊")
            return "這邊還沒做 html要多加彈跳提醒登入方塊"
    else:
        # 在其他情況下也要處理返回有效的回應
        return "Invalid request method"

@app.route("/recommendation")
#@login_required
def recommendation():
    return render_template('recommendation.html',user=g.user)


     
@app.route("/collection", methods=['GET','POST'])
@login_required
def collection():
    if request.method == 'GET':
        collection_kw_nm=user_collection_loader()
        ####加入比對關鍵字的方法 抓新聞
        return render_template('collection.html',collection_kw_nm=collection_kw_nm,user=g.user)
    elif request.method == 'POST':
        selected_value = request.form.get("selectedValue")
        result = f"Received selected value: {selected_value}"
        print(selected_value)
        return jsonify(result)
    
@app.route("/collection/熱門/當週")
@login_required
def collection_week():
    return render_template('collection_week.html')

@app.route("/collection/熱門/當月")
@login_required
def collection_month():
    return render_template('collection_month.html')    

@app.route("/logout")
@login_required
def logout():
    # 登出用户
    logout_user()

    # 移除会话的持久性
    session.permanent = False

    # 移除会话数据
    session.clear()

    # 重定向到登录页或其他页面
    return redirect(url_for('login'))




# 啟動網站伺服器
if __name__ == '__main__':
    app.run(debug=True)
