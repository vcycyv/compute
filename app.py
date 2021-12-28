import json
import os
import pickle
import tempfile
from io import StringIO

from subprocess import check_output
from urllib.parse import urlparse

import flask
import pandas as pd
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
    folder_id = body['folderId']
    description = body['description']
    function = body['function']
    algorithm = body['algorithm']

    token = request.headers.get('Authorization')
    resp = requests.get(train_table, headers={"Authorization": token})
    df = pd.read_csv(StringIO(resp.text))
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
        'folderId': folder_id,
        'description': description,
        'function': function,
        'algorithm': algorithm
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

# serve form request, example:
# file: pickle file
# scoreOutputTable: table name
# scoreInputTable: in form of http://127.0.0.1:8000/dataSources/xxxxxx
# drawerId: drawerId
@app.route('/score', methods=['POST'])
def score():
    model_pickle = request.files['file']

    score_input_table = request.form['scoreInputTable']
    score_output_table_name = request.form['scoreOutputTable']
    drawer_id = request.form['drawerId']
    token = request.headers.get('Authorization')
    resp = requests.get(score_input_table + "/content", headers={"Authorization": token})
    scoring_input = pd.read_csv(StringIO(resp.text))
    print('score output table shape:' + ','.join(str(x) for x in scoring_input.shape))

    temp_dir = tempfile.TemporaryDirectory()
    temp_file_path = os.path.join(temp_dir.name, secure_filename(model_pickle.filename))
    model_pickle.save(temp_file_path)
    print('model pickle file:' + temp_file_path)
    model = pickle.load(open(temp_file_path, 'rb'))
    predictions = model.predict(scoring_input)

    predictions = pd.DataFrame(predictions, columns=['output'])
    scoring_input = scoring_input.reset_index(drop=True)
    result = pd.concat([scoring_input, predictions], axis=1)
    scoring_output_file_name = os.path.join(temp_dir.name, secure_filename(score_output_table_name + '.csv'))
    print('output file:' + scoring_output_file_name)
    result.to_csv(scoring_output_file_name)

    host_port = _get_host(score_input_table)
    print('host and port:' + host_port)
    file_dict = {
        'file': (score_output_table_name + '.csv', open(scoring_output_file_name, 'rb').read())
    }
    data = {
        'drawerId': drawer_id
    }
    response = requests.post(host_port + '/dataSources', files=file_dict, data=data, headers={"Authorization": token})
    print('response.content:' + response.content.decode('utf-8'))
    json_object = json.loads(response.content)
    response = app.response_class(
        response=json.dumps(json_object, indent=2),
        mimetype='application/json',
        status=201
    )

    os.remove(scoring_output_file_name)

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
