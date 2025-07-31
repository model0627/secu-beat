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

```bash
# 저장소 클론
git clone <repository-url>
cd secu-beat

# 설치 스크립트 실행 (root 권한 필요)
sudo ./install.sh

# 또는 수동 설치
sudo python3 -m pip install -r requirements.txt
sudo cp secu-beat.service /etc/systemd/system/
sudo systemctl enable secu-beat
```

## 사용법

### 1. 콘솔 출력 모드
```bash
sudo python3 secu-beat.py --output console
```

### 2. 관리서버 전송 모드
```bash
sudo python3 secu-beat.py --output server --server-url http://your-server.com/api/logs
```

### 3. 설정 파일 사용
```bash
sudo python3 secu-beat.py --config /etc/secu-beat/config.json
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

## 출력 형식

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

## 라이선스

MIT License 