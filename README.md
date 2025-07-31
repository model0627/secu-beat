# SecuBeat - Linux Command Tracker

리눅스 서버에서 SSH 접속 사용자들의 명령어 실행을 실시간으로 추적하고 모니터링하는 시스템입니다.

## 주요 기능

- **실시간 명령어 추적**: SSH로 접속한 사용자들의 모든 명령어 실행을 실시간으로 감지
- **상세 정보 수집**: 사용자명, 접속 IP, 실행 명령어, 명령어 결과, 실행 시간 등을 수집
- **다양한 출력 방식**: 콘솔 출력 또는 JSON 형태로 관리서버 전송
- **보안 감사**: 시스템 보안 감사 및 사용자 활동 모니터링

## 시스템 요구사항

- Linux (Ubuntu 18.04+, CentOS 7+, RHEL 7+ 등)
- Python 3.6+
- auditd 패키지
- root 권한 (audit 로그 접근을 위해 필요)

## 설치 방법

### 1. 자동 설치 (권장)

```bash
# 저장소 클론
git clone <repository-url>
cd secu-beat

# 자동 설치 스크립트 실행 (root 권한 필요)
sudo ./install.sh
```

이 방법은 다음을 자동으로 수행합니다:
- 시스템 의존성 설치 (auditd, python3-venv 등)
- Python 가상환경 생성
- SecuBeat 설치 및 설정
- systemd 서비스 등록
- audit 규칙 설정

### 2. 수동/개발용 설치

```bash
# 일반 사용자 권한으로 홈 디렉토리에 설치
./manual-install.sh
```

### 3. 기존 방식 (externally-managed-environment 에러 해결)

최신 우분투/데비안에서 발생하는 `externally-managed-environment` 에러를 해결했습니다:

```bash
# 가상환경을 사용한 수동 설치
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 또는 시스템 패키지 강제 설치 (권장하지 않음)
sudo pip install -r requirements.txt --break-system-packages
```

## 사용법

### 1. 콘솔 출력 모드
```bash
# 자동 설치 후
sudo secu-beat --output console

# 수동 설치 후
sudo ~/secu-beat/run-secu-beat.sh --output console
```

### 2. 관리서버 전송 모드
```bash
sudo secu-beat --output server --server-url http://your-server.com/api/logs
```

### 3. 설정 파일 사용
```bash
sudo secu-beat --config /etc/secu-beat/config.json
```

### 4. 서비스로 실행
```bash
# 서비스 시작
sudo systemctl start secu-beat

# 서비스 상태 확인
sudo systemctl status secu-beat

# 로그 확인
sudo journalctl -u secu-beat -f

# 부팅 시 자동 시작 설정
sudo systemctl enable secu-beat
```

## 설정

설정은 `/etc/secu-beat/config.json` 파일을 통해 관리됩니다:

```json
{
  "output_mode": "console",
  "server_url": "http://management-server.com/api/logs",
  "server_token": "your-auth-token",
  "log_level": "INFO",
  "excluded_commands": ["ls", "pwd"],
  "included_users": ["*"],
  "excluded_users": ["root"]
}
```

### 환경변수를 통한 설정

```bash
export SECUBEAT_OUTPUT_MODE=server
export SECUBEAT_SERVER_URL=https://your-server.com/api/logs
export SECUBEAT_SERVER_TOKEN=your-token
sudo -E secu-beat
```

## 출력 형식

### 콘솔 출력 (컬러)
```
[2024-01-15T10:30:45Z] john@192.168.1.100 $ cat /etc/passwd (exit: 0)
[2024-01-15T10:30:47Z] admin@192.168.1.50 $ sudo systemctl restart nginx (exit: 0)
```

### JSON 형식
```json
{
  "timestamp": "2024-01-15T10:30:45Z",
  "user": "john",
  "source_ip": "192.168.1.100", 
  "command": "cat /etc/passwd",
  "result": "root:x:0:0:root:/root:/bin/bash\n...",
  "exit_code": 0,
  "session_id": "pts/0",
  "pid": 1234
}
```

## 관리서버 예제

프로젝트에 포함된 Flask 기반 관리서버:

```bash
cd examples/
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-server.txt
python3 management-server.py
```

## 문제 해결

### 1. externally-managed-environment 에러
```bash
# 해결책 1: 자동 설치 스크립트 사용 (가상환경 자동 생성)
sudo ./install.sh

# 해결책 2: 수동으로 가상환경 생성
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. audit 로그 접근 권한 에러
```bash
# auditd 서비스 확인
sudo systemctl status auditd

# audit 규칙 확인
sudo auditctl -l

# 로그 파일 권한 확인
sudo ls -la /var/log/audit/
```

### 3. 의존성 설치 에러
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3-venv python3-full auditd

# CentOS/RHEL
sudo yum install python3-venv audit
```

## 라이선스

MIT License 