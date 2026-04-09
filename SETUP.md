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

## 2. Docker で go2_ros2_sdk を運用する

このリポジトリにはすでに Dockerfile があります。

- ベースイメージ: `ros:humble-ros-base`
- 定義ファイル: [docker/Dockerfile](docker/Dockerfile)
- Compose 定義: [docker/docker-compose.yml](docker/docker-compose.yml)

### 2.1 運用方針

`docker compose up --build` は便利ですが、毎回これを使うとイメージの再ビルド確認や必要に応じたコンテナ再作成が入ります。

コンテナ内で自分が行った変更を残したまま停止と再起動をしたい場合は、以下のように手順を分ける運用の方が分かりやすいです。

- 初回だけ: イメージをビルドする
- 初回だけ: コンテナを作成する
- 普段の利用: `start` で起動する
- 作業するとき: `exec` でコンテナに入る
- 終わったら: `stop` で止める

注意:
- `stop` / `start` では、同じコンテナを使い続けるため、コンテナ内の変更は通常そのまま残ります。
- `down`、`rm`、`up --build --force-recreate` などでコンテナが再作成されると、コンテナ内だけに存在していた変更は失われます。
- 永続的に残したいコード変更は、可能ならホスト側のリポジトリで管理してください。

### 2.2 イメージをビルドする

初回、または `Dockerfile` や依存関係を変更したときだけ実行します。

```bash
cd ~/ros2_ws/src/go2_ros2_sdk/docker
docker compose build
```

- `docker/Dockerfile` に従って Docker イメージを作成します。
- ビルド中にソースコードのコピー、`pip install -r requirements.txt`、`rosdep install`、`colcon build` が実行されます。
- この段階では、まだコンテナは作成も起動もされません。

### 2.3 コンテナを作成する

初回だけ実行します。ここで `ROBOT_IP` と `CONN_TYPE` をコンテナ設定として埋め込みます。

```bash
cd ~/ros2_ws/src/go2_ros2_sdk/docker
ROBOT_IP=<ROBOT_IP> CONN_TYPE=<webrtc_or_cyclonedds> docker compose create
```

例:

```bash
cd ~/ros2_ws/src/go2_ros2_sdk/docker
ROBOT_IP=192.168.5.113 CONN_TYPE=webrtc docker compose create
```

- `docker-compose.yml` に基づいてコンテナを作成します。
- `ROBOT_IP` と `CONN_TYPE` は、このコンテナの環境変数として保存されます。
- コンテナはまだ停止状態で、`ros2 launch go2_robot_sdk robot.launch.py` もまだ実行されません。

補足:
- `ROBOT_IP` を変更したい場合は、既存コンテナを一度 `docker compose down` してから `create` をやり直してください。

### 2.4 コンテナを起動する

2回目以降の通常起動はこれで十分です。

```bash
cd ~/ros2_ws/src/go2_ros2_sdk/docker
docker compose start
```

このリポジトリでは、コンテナ起動時に [docker/Dockerfile](docker/Dockerfile) の `CMD` により `ros2 launch go2_robot_sdk robot.launch.py` が自動で実行されます。

何が起こるか:
- すでに作成済みのコンテナを起動します。
- コンテナのメインプロセスとして `ros2 launch go2_robot_sdk robot.launch.py` が実行されます。
- その launch の中で `go2_driver_node`、`rviz2`、SLAM、Nav2 など複数の ROS 2 ノードが起動します。
- 同じコンテナを再利用するため、通常はコンテナ内で行った変更も残ります。

### 2.5 コンテナの中に入る

起動中のコンテナにシェルで入って作業したい場合は次を実行します。

```bash
cd ~/ros2_ws/src/go2_ros2_sdk/docker
docker compose exec unitree_ros bash
```

何が起こるか:
- 起動中の `unitree_ros` コンテナの中で、追加の `bash` プロセスを開きます。
- すでに動いている `ros2 launch ...` はそのまま継続します。
- 別ターミナルから `ros2 topic pub`、`ros2 topic echo`、`ros2 node list` などを実行できるようになります。

### 2.6 コンテナを停止する

作業内容を残したまま一旦止めるだけなら `stop` を使います。

```bash
cd ~/ros2_ws/src/go2_ros2_sdk/docker
docker compose stop
```

何が起こるか:
- 起動中のコンテナを停止します。
- コンテナ自体は削除されないので、次回 `docker compose start` で同じコンテナを再利用できます。
- コンテナ内だけに存在している変更も、通常はこの時点では残ります。

### 2.7 コンテナを削除して作り直す

設定を変えたい場合や、コンテナを作り直したい場合だけ実行します。

```bash
cd ~/ros2_ws/src/go2_ros2_sdk/docker
docker compose down
```

そのあと、必要なら再度次を行います。

```bash
ROBOT_IP=<ROBOT_IP> CONN_TYPE=<webrtc_or_cyclonedds> docker compose create
docker compose start
```

何が起こるか:
- Compose が管理しているコンテナを停止して削除します。
- 次に `create` すると、新しいコンテナが作られます。
- 以前のコンテナ内だけにあった変更は失われます。
- イメージ自体は通常そのまま残るため、再度 `build` しなくても `create` は可能です。

### 2.8 一発でビルドして起動したい場合

初回確認や使い捨て運用なら、従来通り次でも構いません。

```bash
cd ~/ros2_ws/src/go2_ros2_sdk/docker
ROBOT_IP=<ROBOT_IP> CONN_TYPE=<webrtc_or_cyclonedds> docker compose up --build
```

ただし、この方法は日常的な再起動手順としてはやや重く、コンテナ再作成が入るとコンテナ内の変更が消える可能性があります。

何が起こるか:
- 必要に応じてイメージのビルドを行います。
- その後、コンテナを作成または再作成して起動します。
- 起動時に `ros2 launch go2_robot_sdk robot.launch.py` も自動で実行されます。
- 初回確認には便利ですが、普段の運用では `build`、`create`、`start` を分けた方が挙動を把握しやすいです。

### 2.9 GUI を使う場合の補足

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
