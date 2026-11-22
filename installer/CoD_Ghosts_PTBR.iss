; =====================================================================================
;  Call of Duty: Ghosts (PC) - Tradução + Dublagem PT-BR completa
;  (textos e legendas + cutscenes + vídeos de carregamento + VO in-game a partir do PS4)
; -------------------------------------------------------------------------------------
;  Compilar:  ISCC.exe CoD_Ghosts_PTBR.iss      (payload em .\payload, gerado por make_payload.py)
; =====================================================================================
#define AppVer "1.0.2"

[Setup]
AppId={{6C1B2E8A-5D3F-4F1E-9A7B-PTBR-GHOSTS-VO1}
AppName=Call of Duty: Ghosts - Tradução e Dublagem PT-BR Completa
AppVersion={#AppVer}
AppPublisherURL=https://github.com/yuresl
AppPublisher=Tradução: Tribo Gamer - Dublagem oficial portada do PS4 por yuresl
DefaultDirName={code:DiretorioPadrao}
AppendDefaultDirName=no
DirExistsWarning=no
DisableProgramGroupPage=yes
UsePreviousAppDir=yes
Uninstallable=yes
UninstallFilesDir={app}\_ptbr_desinstalador
UninstallDisplayName=Call of Duty: Ghosts - Tradução e Dublagem PT-BR
OutputDir=output
OutputBaseFilename=CoD_Ghosts_PTBR_Completo_v{#AppVer}
Compression=lzma2/fast
SolidCompression=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=commandline dialog
WizardStyle=modern
ExtraDiskSpaceRequired=2100000000
SetupLogging=yes
InfoBeforeFile=LEIA-ME.txt

[Languages]
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
; textos, legendas, interface e zonas dubladas -> <jogo>\portuguese
Source: "payload\portuguese\*"; DestDir: "{app}\portuguese"; Flags: ignoreversion
; dados temporários: trechos PT dos paks, patches dos vídeos, manifesto e aplicador
Source: "payload\paks\*";     DestDir: "{tmp}\ptbr\paks"; Flags: deleteafterinstall
Source: "payload\bik\*";      DestDir: "{tmp}\ptbr\bik";  Flags: deleteafterinstall
Source: "payload\manifest.txt"; DestDir: "{tmp}\ptbr"; Flags: deleteafterinstall
Source: "payload\tools\hpatchz.exe"; DestDir: "{tmp}\ptbr"; Flags: deleteafterinstall
Source: "payload\tools\HDiffPatch-LICENSE.txt"; DestDir: "{app}\_ptbr_desinstalador"; Flags: ignoreversion
Source: "LEIA-ME.txt"; DestDir: "{app}"; DestName: "LEIA-ME_PTBR.txt"; Flags: ignoreversion

[Code]
const
  BACKUP = '_ptbr_backup';

var
  Falhas: TStringList;

{ ---------------------------------------------------------------- pasta padrão }
function DiretorioPadrao(Param: String): String;
var
  Steam: String;
begin
  Result := 'C:\Games\Call of Duty Ghosts';
  if RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Valve\Steam', 'InstallPath', Steam) or
     RegQueryStringValue(HKCU, 'SOFTWARE\Valve\Steam', 'SteamPath', Steam) then
    if FileExists(AddBackslash(Steam) + 'steamapps\common\Call of Duty Ghosts\iw6sp64_ship.exe') then
      Result := AddBackslash(Steam) + 'steamapps\common\Call of Duty Ghosts';
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  D: String;
begin
  Result := True;
  if CurPageID = wpSelectDir then
  begin
    D := AddBackslash(WizardDirValue);
    if not FileExists(D + 'iw6sp64_ship.exe') or not FileExists(D + 'english\eng_soundfile1.pak') then
    begin
      MsgBox('Não encontrei o Call of Duty: Ghosts nessa pasta.' + #13#10 +
             'Escolha a pasta onde está o arquivo iw6sp64_ship.exe (com a subpasta "english").',
             mbError, MB_OK);
      Result := False;
    end;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  rc: Integer;
begin
  Result := '';
  { jogo aberto? }
  if Exec(ExpandConstant('{cmd}'), '/c tasklist /FI "IMAGENAME eq iw6sp64_ship.exe" | find /I "iw6sp64_ship.exe" > nul',
          '', SW_HIDE, ewWaitUntilTerminated, rc) and (rc = 0) then
    Result := 'Feche o Call of Duty: Ghosts antes de instalar.';
end;

{ ---------------------------------------------------------------- utilidades }
procedure Status(const S: String);
begin
  WizardForm.StatusLabel.Caption := S;
  WizardForm.FilenameLabel.Caption := '';
  WizardForm.Refresh;
end;

function Campo(const Linha: String; Idx: Integer): String;
var
  S: String; I, P: Integer;
begin
  S := Linha + '|';
  for I := 0 to Idx - 1 do
  begin
    P := Pos('|', S);
    Delete(S, 1, P);
  end;
  Result := Copy(S, 1, Pos('|', S) - 1);
end;

function TamanhoArquivo(const F: String): Int64;
var
  S: TFileStream;
begin
  Result := -1;
  try
    S := TFileStream.Create(F, fmOpenRead or fmShareDenyNone);
    try
      Result := S.Size;
    finally
      S.Free;
    end;
  except
  end;
end;

function Anexar(const Destino, Trecho: String): Boolean;
var
  D, T: TFileStream;
begin
  Result := False;
  try
    D := TFileStream.Create(Destino, fmOpenReadWrite);
    try
      T := TFileStream.Create(Trecho, fmOpenRead);
      try
        D.Seek(0, soFromEnd);
        D.CopyFrom(T, T.Size, 1048576);
        Result := True;
      finally
        T.Free;
      end;
    finally
      D.Free;
    end;
  except
    Log('Falha ao anexar ' + Trecho + ': ' + GetExceptionMessage);
  end;
end;

{ ---------------------------------------------------------------- backup antes de copiar }
procedure FazerBackup;
var
  App, Bk: String;
begin
  App := ExpandConstant('{app}\');
  Bk := App + BACKUP + '\';
  ForceDirectories(Bk);
  { pasta portuguese existente (tradução anterior ou nada): renomeia, se ainda não houver backup }
  if DirExists(App + 'portuguese') then
  begin
    if not DirExists(Bk + 'portuguese') then
    begin
      if not RenameFile(App + 'portuguese', Bk + 'portuguese') then
        RaiseException('Não consegui fazer backup da pasta portuguese.');
    end
    else
      DelTree(App + 'portuguese', True, True, True);   { reinstalação: backup original já guardado }
  end;
  ForceDirectories(App + 'portuguese');
end;

{ ---------------------------------------------------------------- pós-cópia: paks e vídeos }
procedure GerarPaksEVideos;
var
  App, Tmp, Bk, L, N, Eng, Dst, Trecho, Nome, Orig, Novo: String;
  Man: TArrayOfString;
  I, Total, Feito, rc: Integer;
begin
  App := ExpandConstant('{app}\');
  Tmp := ExpandConstant('{tmp}\ptbr\');
  Bk := App + BACKUP + '\';
  if not LoadStringsFromFile(Tmp + 'manifest.txt', Man) then
    RaiseException('Manifesto ausente.');
  Total := GetArrayLength(Man);
  WizardForm.ProgressGauge.Min := 0;
  WizardForm.ProgressGauge.Max := Total;
  Feito := 0;
  for I := 0 to Total - 1 do
  begin
    L := Trim(Man[I]);
    if L = '' then Continue;
    if Campo(L, 0) = 'PAK' then
    begin
      N := Campo(L, 1);
      Eng := App + 'english\eng_soundfile' + N + '.pak';
      Dst := App + 'portuguese\por_soundfile' + N + '.pak';
      Status('Gerando áudio PT-BR: por_soundfile' + N + '.pak');
      if (TamanhoArquivo(Eng) <> StrToInt64(Campo(L, 2))) or (GetMD5OfFile(Eng) <> Campo(L, 3)) then
        Falhas.Add('eng_soundfile' + N + '.pak não é a versão esperada (pak não gerado)')
      else if not CopyFile(Eng, Dst, False) then
        Falhas.Add('não consegui copiar eng_soundfile' + N + '.pak')
      else
      begin
        if Campo(L, 6) = '1' then
        begin
          Trecho := Tmp + 'paks\por_soundfile' + N + '.ptbr';
          if not Anexar(Dst, Trecho) then
            Falhas.Add('falha ao anexar o áudio PT em por_soundfile' + N + '.pak');
        end;
        if (TamanhoArquivo(Dst) <> StrToInt64(Campo(L, 4))) or (GetMD5OfFile(Dst) <> Campo(L, 5)) then
          Falhas.Add('por_soundfile' + N + '.pak gerado com conteúdo inesperado');
      end;
    end
    else if Campo(L, 0) = 'BIK' then
    begin
      Nome := Campo(L, 1);
      Status('Aplicando áudio PT-BR no vídeo: ' + Nome);
      Orig := App + Nome;
      { o original vai para o backup (se ainda não estiver lá) }
      if FileExists(Orig) and not FileExists(Bk + Nome) then
        if (TamanhoArquivo(Orig) = StrToInt64(Campo(L, 2))) then
          RenameFile(Orig, Bk + Nome);
      if (not FileExists(Bk + Nome)) or (GetMD5OfFile(Bk + Nome) <> Campo(L, 3)) then
        Falhas.Add(Nome + ': vídeo original não é a versão esperada (mantido como está)')
      else
      begin
        Novo := App + Nome + '.novo';
        if Exec(Tmp + 'hpatchz.exe', '-f "' + Bk + Nome + '" "' + Tmp + 'bik\' + ChangeFileExt(Nome, '.hdiff') +
                '" "' + Novo + '"', '', SW_HIDE, ewWaitUntilTerminated, rc) and (rc = 0) and
           (GetMD5OfFile(Novo) = Campo(L, 5)) then
        begin
          DeleteFile(Orig);
          RenameFile(Novo, Orig);
        end
        else
        begin
          DeleteFile(Novo);
          if not FileExists(Orig) then CopyFile(Bk + Nome, Orig, False);
          Falhas.Add(Nome + ': falha ao aplicar o patch (vídeo original mantido)');
        end;
      end;
    end;
    Feito := Feito + 1;
    WizardForm.ProgressGauge.Position := Feito;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
  begin
    Falhas := TStringList.Create;
    FazerBackup;
  end
  else if CurStep = ssPostInstall then
  begin
    GerarPaksEVideos;
    if Falhas.Count > 0 then
      MsgBox('A instalação terminou com avisos:' + #13#10#13#10 + Falhas.Text + #13#10 +
             'Detalhes no log de instalação.', mbInformation, MB_OK);
    Falhas.Free;
  end;
end;

{ ---------------------------------------------------------------- desinstalação: restaura o backup }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  App, Bk: String;
  R: TFindRec;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    App := ExpandConstant('{app}\');
    Bk := App + BACKUP + '\';
    { vídeos }
    if FindFirst(Bk + '*.bik', R) then
    try
      repeat
        DeleteFile(App + R.Name);
        RenameFile(Bk + R.Name, App + R.Name);
      until not FindNext(R);
    finally
      FindClose(R);
    end;
    { pasta portuguese }
    DelTree(App + 'portuguese', True, True, True);
    if DirExists(Bk + 'portuguese') then
      RenameFile(Bk + 'portuguese', App + 'portuguese');
    RemoveDir(Bk);
  end;
end;
