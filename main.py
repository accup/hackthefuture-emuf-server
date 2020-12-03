from flask import Flask, render_template, request, send_file
import time
import os
import json
import folium
# firebase
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import datetime

# csv関連
import csv
import pprint

# # グラフ描画
# import numpy as np
# import matplotlib.pyplot as plt


app = Flask(__name__)


def initialze_firebase():
    # 証明書情報を環境変数から取得
    if 'FIREBASE_CREDENTIALS_PATH' in os.environ:
        # ファイル名から
        cert = os.environ['FIREBASE_CREDENTIALS_PATH']
    else:
        # JSON文字列から
        cert = json.loads(os.environ['FIREBASE_CREDENTIALS_JSON'])
    cred = credentials.Certificate(cert)
    # Firebaseの初期化
    firebase_admin.initialize_app(cred)


initialze_firebase()

STORE_NUM = 3
PRODUCT_NUM = 1
ZOUKA_NUM = 50
LIMIT_NUM = 4

emergency_flag = True
form_sum = 0
store_num_now = 0


db = firestore.client()


@app.route('/')
def hello():
    name = "Hello World"
    return name


@app.route('/map')
def map():
    folium_map = folium.Map(location=[35.690921, 139.700258], zoom_start=15)

    # firebase全検索
    users_ref = db.collection('ToiletPaper')
    docs = users_ref.stream()

    # csvファイル読み込み
    with open('tenpo_list.csv', 'r') as f:
        reader = csv.reader(f)
        line = [row for row in reader]
        # print(line)

    # 検索結果がdocに格納
    for doc in docs:
        # print(u'{} => {}'.format(doc.id, doc.to_dict()))

        # csvファイルに書き込まれたデータを格納した変数[line]から一致した店舗IDの店舗名、緯度、経度を取得
        # マーカーとしてマップに表示
        for i in line:
            if doc.id in i:
                result = True
                folium.Marker(
                    location=[i[1], i[2]],
                    popup=str(i[3]) + '在庫' +
                    str(doc.to_dict()['num']) + '個',
                    icon=folium.Icon(color='blue', icon='info-sign')
                ).add_to(folium_map)
                break

    # マップをHTMLとして保存
    os.makedirs('templates/cache/', exist_ok=True)
    folium_map.save('templates/cache/map4.html')

    # マップのHTMLを返す
    return render_template('cache/map4.html')


@app.route('/upload_purchase_history', methods=['POST'])
def upload_purchase_history():
    global store_num_now

    # 送信されたデータを取得
    storeID = int(request.json['storeID'])
    print('店舗ID: ' + str(request.json['storeID']))
    productID = int(request.json['productID'])
    print('商品ID: ' + str(request.json['productID']))
    num = int(request.json['num'])
    print('在庫数: ' + str(request.json['num']))
    plus_num = int(request.json['plus_num'])
    print('仕入れ数: ' + str(request.json['plus_num']))

    # 受信時刻（現在時刻）を取得
    now = datetime.datetime.now(datetime.timezone(
        datetime.timedelta(hours=9)))  # 日本時刻
    print(now.strftime('%Y%m%d%H%M%S'))  # yyyyMMddHHmmss形式で出力

    # 何の商品か判別
    # 今回はトイレットペーパとする
    if productID == 1:
        collection_name = 'ToiletPaper'

    # 履歴データベースに保存
    doc_ref = db.collection(
        collection_name + '_history').document(str(now.strftime('%Y-%m-%d-%H-%M-%S-%f')))
    doc_ref.set({
        'storeID': storeID,
        'num': num,
        'plus_num': plus_num,
        'datetime': str(now.strftime('%Y-%m-%d-%H-%M-%S-%f'))
    })

    # 現在の在庫数をリアルタイムデータベースを保存
    doc_ref = db.collection(collection_name).document(str(storeID))
    doc_ref.set({
        'num': num
    })

    store_num_now += 1
    if store_num_now == STORE_NUM:
        global emergency_flag
        count = 0
        num1 = 0
        num2 = 0
        plus_today = 0
        # 降順に3つ取得
        users_ref = db.collection(u'ToiletPaper_history').order_by(
            'datetime', direction=firestore.Query.DESCENDING).limit(STORE_NUM * 2)
        docs = users_ref.stream()
        for doc in docs:
            # print(u'{} => {}'.format(doc.id, doc.to_dict()))
            # print(doc.to_dict()['num'])
            count += 1
            if count > STORE_NUM:
                num1 += doc.to_dict()['num']
            elif count <= STORE_NUM:
                num2 += doc.to_dict()['num']
                plus_today += doc.to_dict()['plus_num']
        print("1日で減った在庫数は" +
              str(num1 - num2 + plus_today) + "個")
        store_num_now = 0

        if num1-num2+plus_today > ZOUKA_NUM:
            print("需要増加検知！！！！！！！！！！！！！")
            emergency_flag = True
            # 製造メーカーに増量依頼
            print(emergency_flag)

    name = "Hello World"
    return name


@app.route('/get_limits', methods=['POST'])
def get_limits():
    if not emergency_flag:
        return ""

    # 送信されたデータを取得
    mynumber = int(request.json['mynumber'])
    print('マイナンバー: ' + str(request.json['mynumber']))

    now = datetime.datetime.now(datetime.timezone(
        datetime.timedelta(hours=9)))  # 日本時刻

    # 顧客データベースに保存or追加
    product_limits = []
    for productID in range(1, 1 + PRODUCT_NUM):
        doc_ref = db.collection('customer').document(
            str(mynumber) + '_' + str(productID))
        doc = doc_ref.get()
        if not doc.exists:
            doc_ref.set({
                'limit_num': LIMIT_NUM,
                'datetime': str(now.strftime('%Y-%m-%d-%H-%M-%S-%f'))
            })
            doc = doc_ref.get()
        product_limits.append((productID, doc.to_dict()['limit_num']))

    return '\n'.join(
        '{},{}'.format(productID, limit_num)
        for productID, limit_num in product_limits
    )


@app.route('/check_mynumber', methods=['POST'])
def check_mynumber():

    if emergency_flag == True:
        # 送信されたデータを取得
        productID = int(request.json['productID'])
        print('商品ID: ' + str(request.json['productID']))
        storeID = int(request.json['storeID'])
        print('店舗ID: ' + str(request.json['storeID']))
        num = int(request.json['num'])
        print('購入個数: ' + str(request.json['num']))
        mynumber = int(request.json['mynumber'])
        print('マイナンバー: ' + str(request.json['mynumber']))

        now = datetime.datetime.now(datetime.timezone(
            datetime.timedelta(hours=9)))  # 日本時刻
        print(now.strftime('%Y%m%d%H%M%S'))  # yyyyMMddHHmmss形式で出力

        # 顧客データベースに保存or追加
        doc_ref = db.collection('customer').document(
            str(mynumber) + '_' + str(productID))
        doc = doc_ref.get()
        if not doc.exists:
            doc_ref.set({
                'limit_num': LIMIT_NUM,
                'datetime': str(now.strftime('%Y-%m-%d-%H-%M-%S-%f'))
            })
            doc = doc_ref.get()

        current_limit_num = doc.to_dict()['limit_num']
        if num <= current_limit_num:
            # 購入成功
            doc_ref.update({
                'limit_num': current_limit_num - num,
                'datetime': str(now.strftime('%Y-%m-%d-%H-%M-%S-%f'))
            })
            print('{}さんが{:4}個購入しました'.format(mynumber, num))

            # 店舗別在庫の更新
            doc_ref = db.collection('ToiletPaper').document(str(storeID))

            rest_num = doc_ref.get().to_dict()['num']
            doc_ref.set({
                'num': rest_num - num
            })
            print('店舗{}の在庫残り{}個'.format(storeID, rest_num - num))

            return "購入許可"
        else:
            # 購入失敗
            print('{}さんは購入に失敗しました'.format(mynumber))
            return "購入不許可"
    else:
        return "ok"


@app.route('/form_request', methods=['POST'])
def form_request():
    global form_sum

    # 送信されたデータを取得
    productID = int(request.json['productID'])
    print('商品ID: ' + str(request.json['productID']))
    num = int(request.json['num'])
    print('増加依頼個数: ' + str(request.json['num']))
    mynumber = int(request.json['mynumber'])
    print('マイナンバー: ' + str(request.json['mynumber']))
    # 証明書も

    if form_sum < num:
        return "not ok"
    form_sum -= num

    now = datetime.datetime.now(datetime.timezone(
        datetime.timedelta(hours=9)))  # 日本時刻
    print(now.strftime('%Y%m%d%H%M%S'))  # yyyyMMddHHmmss形式で出力

    doc_ref = db.collection('customer').document(
        str(mynumber) + '_' + str(productID))
    doc = doc_ref.get()
    if not doc.exists:
        doc_ref.set({
            'limit_num': LIMIT_NUM,
            'datetime': str(now.strftime('%Y-%m-%d-%H-%M-%S-%f'))
        })
        doc = doc_ref.get()
    current_limit_num = doc.to_dict()['limit_num']
    doc_ref.update({
        'limit_num': current_limit_num + num,
        'datetime': str(now.strftime('%Y-%m-%d-%H-%M-%S-%f'))
    })

    return "Request Accepted"


@app.route('/form_trans_request', methods=['POST'])
def form_trans_request():
    global form_sum

    # 送信されたデータを取得
    productID = int(request.json['productID'])
    print('商品ID: ' + str(request.json['productID']))
    num = int(request.json['num'])
    print('増加依頼個数: ' + str(request.json['num']))
    mynumber = int(request.json['mynumber'])
    print('マイナンバー: ' + str(request.json['mynumber']))
    # 証明書も

    now = datetime.datetime.now(datetime.timezone(
        datetime.timedelta(hours=9)))  # 日本時刻
    print(now.strftime('%Y%m%d%H%M%S'))  # yyyyMMddHHmmss形式で出力

    doc_ref = db.collection('customer').document(
        str(mynumber) + '_' + str(productID))
    doc = doc_ref.get()
    if not doc.exists:
        doc_ref.set({
            'limit_num': LIMIT_NUM,
            'datetime': str(now.strftime('%Y-%m-%d-%H-%M-%S-%f'))
        })
        doc = doc_ref.get()
    current_limit_num = doc.to_dict()['limit_num']

    if current_limit_num - num < 0:
        return "not ok"
    form_sum += num
    doc_ref.update({
        'limit_num': current_limit_num - num,
        'datetime': str(now.strftime('%Y-%m-%d-%H-%M-%S-%f'))
    })

    return "Request Accepted"


# @app.route('/aaa', methods=['GET', 'POST'])
# def aaa():

#     # 折れ線グラフを出力
#     left = np.array([1, 2, 3, 4, 5])
#     height = np.array([100, 300, 200, 500, 400])
#     plt.plot(left, height)

#     plt.savefig('templates/cache/figure.png')
#     return send_file('templates/cache/figure.png', mimetype='image/png')


if __name__ == '__main__':
    app.run(debug=True, port=5000)
