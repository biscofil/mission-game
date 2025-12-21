# Mission game

```shell
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python3 app.py

# or
docker build -t biscofil/mission-game:1.0.1 .
docker run --rm -v ${PWD}/volume:/instance -p 8080:5000 biscofil/mission-game:1.0.1
docker run -d --restart unless-stopped -v ${PWD}/volume:/instance -p 8080:5000 biscofil/mission-game:1.0.1
```
