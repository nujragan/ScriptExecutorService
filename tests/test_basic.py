import json
from io import BytesIO
import os


def test_index(application, client):
    res = client.get('/welcome')
    assert res.status_code == 200
    expected = {'hello': 'world'}
    assert expected == json.loads(res.get_data(as_text=True))


def test_file_upload(client):

    data = {
        'field': 'value',
        'file': (BytesIO(b'FILE CONTENT'), 'test.sh')
    }
    filename="test.sh"

    rv = client.post('/SubmitScript', buffered=True,
                     content_type='multipart/form-data',
                     data=data)
    path = "/tmp/ScriptExecutorService/"
    script_basename = "/test"
    assert rv.status_code == 302
    assert os.path.isdir(path+script_basename)
    assert os.path.exists(path+script_basename+'/'+filename)

