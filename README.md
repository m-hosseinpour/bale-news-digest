```shell
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:mozillateam/ppa

echo 'Package: *
Pin: release o=LP-PPA-mozillateam
Pin-Priority: 1001' | sudo tee /etc/apt/preferences.d/mozilla-ppa

sudo apt update
sudo apt install firefox firefox-geckodriver
```

```shell
flask --app bot_webhook run --host 0.0.0.0 --port 8001
#prod:
gunicorn --bind 127.0.0.1:8001 --workers 1 bot_webhook:app
```
