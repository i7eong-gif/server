추천 독서 루트

README / DESIGN
   ↓
App.xaml.cs
   ↓
SettingsService.cs
   ↓
MainWindow.xaml(.cs)
   ↓
QuotePoller.cs
   ↓
SettingsWindow.xaml(.cs)
   ↓
기타 UI 창
   ↓
Symbol / API 관련


KRStockTray
===========

Windows 트레이에 상주하며 한국(KR) / 미국(US) 주식 시세를 실시간으로 보여주는
경량 주식 모니터링 프로그램입니다.

- 트레이 아이콘 + 미니 주가창
- 설정창에서 종목 추가 / 삭제 / 정렬 즉시 반영
- FastAPI 기반 서버와 통신하는 클라이언트 구조
- 단일 EXE 배포 가능


--------------------------------------------------
주요 기능
--------------------------------------------------

- 한국(KR) / 미국(US) 주식 동시 지원
- 미니 주가창 (항상 위, 투명도 조절)
- 종목 설정 창
  * 코드로 추가
  * 종목명 검색(KR)
  * 드래그로 순서 변경
  * 활성 / 비활성 토글
- 설정 변경 즉시 주가창 반영
- 창 위치 / 투명도 자동 저장
- Windows 시스템 트레이 상주


--------------------------------------------------
아키텍처 개요
--------------------------------------------------

[Stock API Server]
        ▲
        │
   QuotePoller
        │
SettingsService (Config + WatchList)
        │
 ┌──────┴────────┐
 │               │
MainWindow   SettingsWindow


--------------------------------------------------
핵심 설계 원칙 (중요)
--------------------------------------------------

1. WatchList는 단 하나만 존재한다
   - AppConfig.WatchList : ObservableCollection<WatchItem>

2. 설정창은 WatchList의 복사본을 만들지 않는다
   - Config를 직접 수정한다

3. UI 갱신은 WPF 바인딩에 맡긴다
   - ObservableCollection
   - INotifyPropertyChanged
   - Items.Refresh() 사용 금지

4. 즉시 반영과 저장은 분리한다
   - NotifyChanged() : UI / Poller 즉시 반영
   - Save() : 디스크 저장 전용


--------------------------------------------------
주요 구성 요소
--------------------------------------------------

[App.xaml.cs]
- 애플리케이션 진입점
- 단일 인스턴스 보장
- 트레이 아이콘 생성
- MainWindow / SettingsWindow 관리


[SettingsService]
- 앱 전체의 단일 상태 관리자 (Single Source of Truth)
- 설정 로드 / 저장
- WatchList 관리
- 설정 변경 이벤트 브로드캐스트

주요 멤버:
- AppConfig Config
- event OnConfigChanged
- NotifyChanged()
- Save()


[AppConfig]
- 사용자 설정 데이터 모델

포함 항목:
- WatchList
- WindowOpacity
- WindowLeft
- WindowTop


[WatchItem]
- 개별 종목 정보

필드:
- Market : KR / US
- Code   : 종목 코드
- Name   : 종목명 (선택)
- IsEnabled : 활성 여부

- INotifyPropertyChanged 구현
- UI 자동 갱신 지원


[QuotePoller]
- 서버에서 주기적으로 시세 조회
- WatchList(IsEnabled = true) 기준으로 조회
- 결과를 MainWindow에 전달
- SettingsService.OnConfigChanged를 통해 즉시 재조회 가능


[MainWindow]
- 트레이 상주 미니 주가창
- 종목 리스트 표시
- 마우스 오버 시 투명도 1.0
- 창 이동 가능
- 위치 / 투명도 디바운스 저장


[SettingsWindow]
- 종목 설정 UI
- WatchList 직접 수정
- 추가 / 삭제 / 이동 즉시 반영
- Poller 직접 접근하지 않음


--------------------------------------------------
설정 변경 흐름
--------------------------------------------------

SettingsWindow
   ↓
Config.WatchList 변경
   ↓
ObservableCollection 자동 UI 갱신
   ↓
SettingsService.NotifyChanged()
   ↓
MainWindow / QuotePoller 반영


--------------------------------------------------
실행 방법
--------------------------------------------------

요구 사항:
- Windows 10 이상
- .NET 8 SDK

개발 실행:
- Visual Studio에서 F5

단일 EXE 배포:
- dotnet publish -c Release -r win-x64


--------------------------------------------------
자주 발생하는 실수
--------------------------------------------------

- WatchList를 List<T>로 변경하지 말 것
- WatchList에 새 컬렉션을 대입하지 말 것
- SettingsWindow에서 Poller 직접 호출 금지
- Items.Refresh() 사용 금지


--------------------------------------------------
향후 확장 아이디어
--------------------------------------------------

- 종목 그룹 / 카테고리
- 가격 알림
- 단축키 지원
- 다중 서버 / 계정
- 차트 미리보기


--------------------------------------------------
라이선스
--------------------------------------------------

개인 프로젝트 / 내부 도구 용도
(라이선스 정책은 필요 시 추가)
