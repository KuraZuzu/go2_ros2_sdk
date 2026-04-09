# go2_ros2_sdk Setup Guide

このファイルは、`go2_ros2_sdk` を Ubuntu 22.04 + ROS 2 Humble 環境でビルド・起動するための手順をまとめたものです。

## 既存の手順がある場所

このリポジトリには、すでに以下の場所にビルド関連の情報があります。

- 通常ビルド手順: [README.md](README.md)
  - `Installation`: 依存関係の導入と `colcon build`
  - `Running via Docker`: Docker Compose での起動例
- Docker イメージ定義: [docker/Dockerfile](docker/Dockerfile)
- Docker Compose 定義: [docker/docker-compose.yml](docker/docker-compose.yml)
- CI のビルド設定: [.github/workflows/ros_build.yaml](.github/workflows/ros_build.yaml)

既存 README には手順が分散しているため、このファイルでは Docker の導入から実行までを通しで整理しています。

## 1. Ubuntu 22.04 に Docker を入れる

以下は Docker 公式の Ubuntu 向け `apt` リポジトリを使う手順です。

参考:
- Docker Engine on Ubuntu: https://docs.docker.com/engine/install/ubuntu/

### 1.1 古い Docker パッケージを削除

必要であれば実施するコマンド
- この手順は、Ubuntu 標準の `docker.io` や旧式の `docker-compose` がすでに入っていて、これから Docker 公式版の `docker-ce` に入れ替えたい場合に実行します。
- まだ Docker を一度も入れていない新規環境なら、実行してもしなくても大きな問題はありませんが、省略して構いません。
- すでに別プロジェクトで Docker を運用していて、現在の Docker 環境に問題がない場合は、むやみに実行しないでください。システムに入っている Docker の実行環境を入れ替える操作なので、稼働中のコンテナや Docker サービスに影響することがあります。
- この手順は主に Docker ツール本体や関連ランタイムを削除するもので、通常は各プロジェクトのソースコード、`Dockerfile`、イメージ、ボリュームを直接削除するものではありません。

```bash
for pkg in docker.io docker-doc docker-compose podman-docker containerd runc; do
  sudo apt-get remove -y "$pkg"
done
```

### 1.2 Docker の公式 GPG key と apt repository を追加

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
```

### 1.3 Docker Engine と Compose plugin をインストール

```bash
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

### 1.4 sudo なしで Docker を使いたい場合

```bash
sudo groupadd docker 2>/dev/null || true
sudo usermod -aG docker $USER
newgrp docker
```

### 1.5 動作確認

```bash
docker --version
docker compose version
sudo docker run hello-world
```

`sudo docker run hello-world` が成功すれば、Docker 自体の導入は完了です。

## 2. Docker で go2_ros2_sdk をビルドして起動する

このリポジトリにはすでに Dockerfile があります。

- ベースイメージ: `ros:humble-ros-base`
- 定義ファイル: [docker/Dockerfile](docker/Dockerfile)
- Compose 定義: [docker/docker-compose.yml](docker/docker-compose.yml)

### 2.1 イメージをビルドする

リポジトリのルートで実行します。

```bash
cd ~/ros2_ws/src/go2_ros2_sdk
docker build -f docker/Dockerfile -t go2_ros2_sdk:humble .
```

### 2.2 Compose で起動する

README では `docker-compose up --build` と書かれていますが、現在の Docker では `docker compose up --build` が標準です。

```bash
cd ~/ros2_ws/src/go2_ros2_sdk/docker
ROBOT_IP=<ROBOT_IP> CONN_TYPE=<webrtc_or_cyclonedds> docker compose up --build
```

例:

```bash
cd ~/ros2_ws/src/go2_ros2_sdk/docker
ROBOT_IP=192.168.12.113 CONN_TYPE=webrtc docker compose up --build
```

### 2.3 GUI を使う場合の補足

`docker/docker-compose.yml` では X11 の socket と `.Xauthority` をマウントしているため、`rviz2` などの GUI をホストに表示したい場合はホスト側の X11 設定が必要です。

必要に応じて実行:

```bash
xhost +SI:localuser:root
```

GUI を使わない場合はこの設定は不要です。

## 3. Docker を使わずに ROS 2 Humble で通常ビルドする

README にある手順を、現在のワークスペース構成向けに並べると次の流れです。

前提:
- Ubuntu 22.04
- ROS 2 Humble
- `rosdep`
- `colcon`

### 3.1 ROS 依存と Python 依存を入れる

```bash
sudo apt-get update
sudo apt-get install -y \
  python3-pip \
  clang \
  portaudio19-dev \
  ros-humble-image-tools \
  ros-humble-vision-msgs
```

### 3.2 Python パッケージを入れる

```bash
cd ~/ros2_ws/src/go2_ros2_sdk
python3 -m pip install -r requirements.txt
```

注意:
- `requirements.txt` には `open3d`、`torch`、`torchvision` などが含まれます。
- README にもある通り、`pip install` が途中で失敗すると一部機能は使えません。

### 3.3 rosdep と colcon build

```bash
cd ~/ros2_ws
source /opt/ros/humble/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build
```

開発用途なら次でも構いません。

```bash
colcon build --symlink-install
```

### 3.4 ビルド後に起動する

```bash
cd ~/ros2_ws
source /opt/ros/humble/setup.bash
source install/setup.bash
export ROBOT_IP="<ROBOT_IP>"
export CONN_TYPE="webrtc"
ros2 launch go2_robot_sdk robot.launch.py
```

CycloneDDS を使う場合:

```bash
export CONN_TYPE="cyclonedds"
```

## 4. どの手順を使うべきか

- まず素早く試したい: Docker
- ROS 2 開発やデバッグを継続的にしたい: ホスト上で通常ビルド
- README の既存箇所を確認したい:
  - 通常ビルドは [README.md](README.md)
  - Docker 起動は [README.md](README.md)
  - 実際のコンテナ定義は [docker/Dockerfile](docker/Dockerfile) と [docker/docker-compose.yml](docker/docker-compose.yml)
