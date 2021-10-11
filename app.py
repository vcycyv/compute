import json
import os
import pickle
import tempfile
from io import StringIO

from subprocess import check_output
from urllib.parse import urlparse

import flask
import pandas
import requests
import sklearn
from flask import Flask, request
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.svm import SVC
from werkzeug.utils import secure_filename

app = Flask(__name__)
uri = ''


@app.route('/code/file', methods=['POST'])
def execute_file():
    code_file = request.files['file']
    temp_dir = tempfile.TemporaryDirectory()
    try:
        code_file.save(os.path.join(temp_dir.name, secure_filename(code_file.filename)))
        stdout = check_output(["python3", temp_dir.name + os.path.sep + code_file.filename])
        return stdout
    finally:
        temp_dir.cleanup()
        return "failed to execute file " + code_file.filename


@app.route('/code', methods=['POST'])
def execute_code():
    code = request.get_data(as_text=True)
    stdout = check_output(["python3", "-c", code]).decode('utf-8')
    return stdout


# example request
# {
# 	"trainTable": "http://127.0.0.1:8000/dataSource/f4dc0dfb-bb94-43ce-b6bb-16d58519d710/content",
# 	"predictors": ["sepal_length","sepal_width","petal_length","petal_width"],
# 	"target": "species",
# 	"modelName":"iris",
# 	"description":"test",
# 	"function": "classification"
# }
@app.route('/models', methods=['POST'])
def build_model():
    body = request.get_json()
    train_table = body['trainTable']
    predictors = body['predictors']
    target = body['target']
    model_name = body['name']
    description = body['description']
    function = body['function']

    token = request.headers.get('Authorization')
    resp = requests.get(train_table, headers={"Authorization": token})
    df = pandas.read_csv(StringIO(resp.text))
    try:
        x = df.loc[:, predictors]
        y = df.loc[:, target]
    except KeyError:
        return "data source " + train_table + " doesn't have required columns", 404
    x_train, x_test, y_train, y_test = sklearn.model_selection.train_test_split(x, y, random_state=1)
    model = SVC(gamma='auto')
    kfold = StratifiedKFold(n_splits=10, random_state=1, shuffle=True)
    cv_result = cross_val_score(model, x_train, y_train, cv=kfold, scoring='accuracy')
    print('%f (%f)' % (cv_result.mean(), cv_result.std()))
    model.fit(x_train, y_train)
    predictions = model.predict(x_test)
    print(accuracy_score(y_test, predictions))
    print(confusion_matrix(y_test, predictions))
    print(classification_report(y_test, predictions))

    fd, path = tempfile.mkstemp()
    with os.fdopen(fd, 'wb') as f:
        pickle.dump(model, file=f)

    host_port = _get_host(train_table)
    file_dict = {
        'files': (model_name + '.pickle', open(path, 'rb').read())
    }
    data = {
        'name': model_name,
        'description': description,
        'function': function
    }
    response = requests.post(host_port + '/models', files=file_dict, data=data, headers={"Authorization": token})
    print('response.content:' + response.content.decode('utf-8'))
    json_object = json.loads(response.content)
    response = app.response_class(
        response=json.dumps(json_object, indent=2),
        mimetype='application/json',
        status=201
    )
    return response


@app.route('/status', methods=['GET'])
def is_alive():
    status_code = flask.Response(status=200)
    return status_code


def _get_host(url):
    parse_result = urlparse(url)
    port = parse_result.port
    if port is None:
        port = '80'
    return 'http://' + parse_result.hostname + ':' + str(port)


if __name__ == "__main__":
    app.run(debug=True)

# @app.route('/datasource', methods=['GET'])
# def load_datasource():
#     url = request.args.get("url")
#     token = request.headers.get('Authorization')
#     resp = requests.get(url, headers={"Authorization": token})
#     # print('resp.text:' + resp.text)
#     df = pandas.read_csv(StringIO(resp.text))
#     print('df.attrs:' + str(df.attrs))
#     print(df.columns)
#     return resp.text
