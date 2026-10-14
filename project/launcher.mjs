import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawn, spawnSync} from 'node:child_process';

const root = path.dirname(fileURLToPath(import.meta.url));
const runtime = path.join(root, '.runtime');
const windows = process.platform === 'win32';
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const services = {
  backend: {entry: path.join(root, 'backend', 'run.py'), cwd: path.join(root, 'backend'), url: 'http://127.0.0.1:8000/api/health'},
  frontend: {entry: path.join(root, 'frontend', 'node_modules', 'vite', 'bin', 'vite.js'), cwd: path.join(root, 'frontend'), url: 'http://127.0.0.1:5173'},
};
const normalize = value => String(value || '').replaceAll('/', '\\').toLowerCase();

function python() {
  const candidates = [];
  if (process.env.QUOTE_PYTHON) candidates.push([process.env.QUOTE_PYTHON, []]);
  if (process.env.USERPROFILE) candidates.push([path.join(process.env.USERPROFILE, '.cache', 'codex-runtimes', 'codex-primary-runtime', 'dependencies', 'python', 'python.exe'), []]);
  candidates.push([path.join(root, 'backend', '.venv', 'Scripts', 'python.exe'), []], [windows ? 'py.exe' : 'python3', windows ? ['-3'] : []], ['python', []]);
  for (const [command, prefix] of candidates) {
    if (path.isAbsolute(command) && !fs.existsSync(command)) continue;
    const result = spawnSync(command, [...prefix, '-c', 'import sys; print(sys.executable)'], {encoding:'utf8', timeout:5000, windowsHide:true});
    if (result.status === 0 && result.stdout.trim()) return result.stdout.trim();
  }
  throw new Error('Python 3.12 이상을 설치하거나 QUOTE_PYTHON에 Python 실행 파일 경로를 지정하세요.');
}

// The query is an ordinary PowerShell command, not a .ps1 file. No execution-policy setting is changed.
function processInfo(pid) {
  if (!Number.isInteger(pid) || pid <= 0) return null;
  if (!windows) return null;
  const command = '$p = Get-CimInstance Win32_Process -Filter ("ProcessId=" + [int]$env:QUOTE_LAUNCH_PID); if ($p) { $p | Select-Object ProcessId,CreationDate,ExecutablePath,CommandLine | ConvertTo-Json -Compress }';
  const result = spawnSync('powershell.exe', ['-NoProfile','-NonInteractive','-Command',command], {encoding:'utf8', timeout:10000, windowsHide:true, env:{...process.env, QUOTE_LAUNCH_PID:String(pid)}});
  if (result.status !== 0) throw new Error('프로젝트 서버의 실행 정보를 확인할 수 없습니다: ' + result.stderr.trim());
  return result.stdout.trim() ? JSON.parse(result.stdout) : null;
}

function owned(info, service) {
  return !!info && normalize(info.CommandLine).includes(normalize(service.entry));
}

function record(name, info) {
  fs.writeFileSync(path.join(runtime, name + '.process.json'), JSON.stringify(info, null, 2));
  fs.writeFileSync(path.join(runtime, name + '.pid'), String(info.ProcessId));
}

function registration(name) {
  const jsonFile = path.join(runtime, name + '.process.json');
  if (fs.existsSync(jsonFile)) return JSON.parse(fs.readFileSync(jsonFile, 'utf8'));
  const oldPid = path.join(runtime, name + '.pid');
  if (!fs.existsSync(oldPid)) return null;
  const info = processInfo(Number(fs.readFileSync(oldPid, 'utf8').replace(/^\uFEFF/, '').trim()));
  if (!owned(info, services[name])) return null;
  record(name, info);
  return info;
}

async function ready(name) {
  try {
    const response = await fetch(services[name].url, {signal:AbortSignal.timeout(1500)});
    if (!response.ok) return false;
    if (name === 'backend') { const data = await response.json(); return data.ok === true && data.mode === 'archive'; }
    return (await response.text()).includes('견적 아카이브');
  } catch { return false; }
}

async function start() {
  fs.mkdirSync(runtime, {recursive:true});
  if (!fs.existsSync(services.frontend.entry)) throw new Error('먼저 .\\setup.cmd 로 라이브러리를 설치하세요.');
  for (const [name, service] of Object.entries(services)) {
    if (await ready(name)) { registration(name); continue; }
    const previous = registration(name);
    if (previous && owned(processInfo(previous.ProcessId), service)) throw new Error(`${name} 서버가 실행 중이지만 응답하지 않습니다. .\\stop.cmd 실행 후 다시 시작하세요.`);
    const command = name === 'backend' ? python() : process.execPath;
    const args = name === 'backend' ? [service.entry] : [service.entry,'--host','127.0.0.1','--port','5173','--strictPort'];
    const output = fs.openSync(path.join(runtime, name + '.log'), 'a');
    const error = fs.openSync(path.join(runtime, name + '-error.log'), 'a');
    let child;
    try {
      child = spawn(command, args, {cwd:service.cwd, detached:true, windowsHide:true, stdio:['ignore',output,error]});
      await new Promise((resolve,reject) => { child.once('spawn',resolve); child.once('error',reject); });
    } finally { fs.closeSync(output); fs.closeSync(error); }
    child.unref();
    const info = processInfo(child.pid);
    if (!owned(info, service)) throw new Error('서버 실행 정보를 확인하지 못했습니다. .runtime 로그를 확인하세요.');
    record(name, info);
  }
  // Initial source enrichment may render and recognize several PDF pages.
  for (let attempt = 0; attempt < 120; attempt++) {
    const checks = await Promise.all([ready('backend'), ready('frontend')]);
    if (checks.every(Boolean)) {
      console.log('실행 완료: http://127.0.0.1:5173');
      console.log('종료: .\\stop.cmd');
      return;
    }
    await sleep(500);
  }
  throw new Error('서버가 준비되지 않았습니다. .runtime의 backend-error.log / frontend-error.log를 확인하세요.');
}

async function stop() {
  for (const name of ['frontend','backend']) {
    const saved = registration(name);
    if (saved) {
      const current = processInfo(saved.ProcessId);
      if (owned(current, services[name]) && current.CreationDate === saved.CreationDate && normalize(current.ExecutablePath) === normalize(saved.ExecutablePath)) {
        process.kill(saved.ProcessId);
        console.log(name + ' 종료 완료');
      } else if (current) console.log(name + ': 기록과 다른 프로세스이므로 종료하지 않았습니다.');
    }
    for (const suffix of ['.pid','.process.json']) {
      const file = path.join(runtime, name + suffix);
      if (fs.existsSync(file)) fs.unlinkSync(file);
    }
  }
  await sleep(400);
}

function run(command, args, cwd) {
  const result = spawnSync(command, args, {cwd, stdio:'inherit', windowsHide:true});
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error('설치가 완료되지 않았습니다. 위 오류를 확인하세요.');
}

function setup() {
  const npmLocations = [path.join(path.dirname(process.execPath), 'node_modules','npm','bin','npm-cli.js'), path.join(path.dirname(process.execPath), '..','node_modules','npm','bin','npm-cli.js')];
  const npmCLI = npmLocations.find(candidate => fs.existsSync(candidate));
  if (!npmCLI) throw new Error('Node.js에 포함된 npm을 찾지 못했습니다. Node.js 24 설치를 확인하세요.');
  console.log('백엔드 라이브러리를 설치합니다.');
  run(python(), ['-m','pip','install','--target',path.join(root,'backend','.packages'),'-r',path.join(root,'backend','requirements.txt')], root);
  console.log('프론트 라이브러리를 설치합니다.');
  run(process.execPath, [npmCLI,fs.existsSync(path.join(root,'frontend','package-lock.json')) ? 'ci' : 'install'], services.frontend.cwd);
  console.log('설치 완료. .\\start.cmd 로 실행하세요.');
}

try {
  const action = process.argv[2];
  if (!windows) throw new Error('이 실행 파일은 Windows용입니다. 다른 환경은 README의 수동 실행 방법을 사용하세요.');
  if (action === 'start') await start();
  else if (action === 'stop') await stop();
  else if (action === 'setup') setup();
  else throw new Error('사용법: node launcher.mjs start | stop | setup');
} catch (error) { console.error(error.message); process.exitCode = 1; }
