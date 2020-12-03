from flask import (
    Flask,
    render_template,
)


app = Flask(__name__)


def initialze_db():
    import firebase_admin
    from firebase_admin import credentials
    from firebase_admin import firestore
    import os
    import json

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
    # FirestoreのDBを取得
    db = firestore.client()
    return db


db = initialze_db()


@app.route('/')
def index():
    misc_ref = db.collection('misc')
    doc_ref = misc_ref.document('hello')
    doc = doc_ref.get()
    if not doc.exists:
        message = '(No message)'
    else:
        message = doc.to_dict()['message']

    return render_template(
        'pages/index.html',
        message=message,
    )
