<script>
  import EntryForm from "./EntryForm.svelte";

  let session = null;
  let view = "logs"; // logs=测量记录 / conv=换算专页
  let logs = [];
  let conversions = [];
  let equivalent = null;
  let loginUser = "surveyor";
  let loginPass = "surv123456";
  let error = "";
  let loading = false;
  let timer;

  // 当量编辑
  let eqFactor = "";
  let eqBaseline = "";
  let eqEditing = false;
  let eqError = "";
  let eqNotice = "";

  $: isWriter = session?.role === "writer";
  $: if (!eqEditing && equivalent) {
    eqFactor = String(equivalent.factor);
    eqBaseline = String(equivalent.baseline_mm);
  }

  function headers() {
    return session ? { Authorization: "Bearer " + session.token } : {};
  }

  function fmt(s) {
    return s ? s.replace("T", " ").slice(0, 19) : "—";
  }

  async function refresh() {
    if (!session) return;
    const opts = { headers: headers() };
    const [logsRes, eqRes, convRes] = await Promise.all([
      fetch("/api/logs", opts),
      fetch("/api/equivalent", opts),
      fetch("/api/conversions", opts),
    ]);
    if (logsRes.status === 401 || eqRes.status === 401 || convRes.status === 401) {
      logout();
      return;
    }
    if (logsRes.ok) logs = await logsRes.json();
    if (eqRes.ok) equivalent = await eqRes.json();
    if (convRes.ok) conversions = await convRes.json();
  }

  async function login() {
    error = "";
    loading = true;
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: loginUser, password: loginPass }),
      });
      const data = await res.json();
      if (!res.ok) {
        error = data.detail || "登录失败";
        return;
      }
      session = { token: data.access_token, username: data.username, role: data.role };
      localStorage.setItem("tunnel_session", JSON.stringify(session));
      await refresh();
      timer = setInterval(refresh, 2000);
    } catch {
      error = "无法连接接口";
    } finally {
      loading = false;
    }
  }

  function logout() {
    if (timer) clearInterval(timer);
    session = null;
    logs = [];
    conversions = [];
    equivalent = null;
    view = "logs";
    localStorage.removeItem("tunnel_session");
  }

  function switchView(v) {
    view = v;
    eqError = "";
    eqNotice = "";
    eqEditing = false;
    refresh();
  }

  async function saveEquivalent() {
    eqError = "";
    eqNotice = "";
    loading = true;
    try {
      const res = await fetch("/api/equivalent", {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...headers() },
        body: JSON.stringify({ factor: eqFactor, baseline_mm: eqBaseline }),
      });
      const data = await res.json();
      if (!res.ok) {
        eqError = data.detail || "保存失败";
        return;
      }
      equivalent = data;
      eqEditing = false;
      eqNotice = "当量已保存，后续弦长按新当量换算";
    } catch {
      eqError = "保存时网络异常";
    } finally {
      loading = false;
    }
  }

  const raw = localStorage.getItem("tunnel_session");
  if (raw) {
    try {
      session = JSON.parse(raw);
      refresh();
      timer = setInterval(refresh, 2000);
    } catch {
      localStorage.removeItem("tunnel_session");
    }
  }
</script>

<style>
  :global(body) {
    margin: 0;
    font-family: "Segoe UI", system-ui, sans-serif;
    background: #1c1917;
    color: #f5f5f4;
  }
  header {
    display: flex; align-items: center; gap: 1rem;
    background: #0c0a09; border-bottom: 1px solid #44403c;
    padding: 0.7rem 1.5rem;
  }
  .brand { color: #fbbf24; font-weight: 700; font-size: 1.1rem; }
  nav { display: flex; gap: 0.5rem; }
  .spacer { flex: 1; }
  .who { color: #a8a29e; font-size: 0.9rem; }
  main { max-width: 1080px; margin: 0 auto; padding: 1.5rem; }
  h1 { color: #fbbf24; margin: 0 0 0.25rem; }
  h2 { margin: 0 0 0.75rem; font-size: 1.05rem; color: #fcd34d; }
  .sub { color: #a8a29e; margin-bottom: 1.25rem; }
  section {
    background: #292524; border: 1px solid #44403c; border-radius: 8px;
    padding: 1rem 1.25rem; margin-bottom: 1rem;
  }
  label { display: block; font-size: 0.85rem; color: #d6d3d1; margin-bottom: 0.25rem; }
  .field {
    width: 100%; box-sizing: border-box; padding: 0.5rem 0.65rem; border-radius: 6px;
    border: 1px solid #57534e; background: #0c0a09; color: #fafaf9; margin-bottom: 0.75rem;
  }
  button {
    cursor: pointer; padding: 0.5rem 1rem; border: none; border-radius: 6px;
    background: #d97706; color: #fff; font-weight: 600;
  }
  button.secondary { background: #57534e; }
  button.nav { background: transparent; color: #d6d3d1; border: 1px solid #57534e; }
  button.nav.active { background: #d97706; border-color: #d97706; color: #fff; }
  .err { color: #fb7185; }
  .okmsg { color: #86efac; }
  .hint { color: #a8a29e; font-size: 0.85rem; }
  .eqgrid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 1rem; max-width: 480px; }
  table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
  th, td { text-align: left; padding: 0.45rem; border-bottom: 1px solid #44403c; }
  .tag { padding: 0.1rem 0.4rem; border-radius: 4px; font-size: 0.8rem; }
  .ok { background: #14532d; color: #86efac; }
  .bad { background: #7f1d1d; color: #fca5a5; }
  .pending { background: #713f12; color: #fde68a; }
  .info { background: #1e3a8a; color: #bfdbfe; }
  .plain { background: #44403c; color: #e7e5e4; }
</style>

<header>
  <span class="brand">隧道收敛测缝台</span>
  {#if session}
    <nav>
      <button class="nav" class:active={view === "logs"} on:click={() => switchView("logs")}>测量记录</button>
      <button class="nav" class:active={view === "conv"} on:click={() => switchView("conv")}>换算专页</button>
    </nav>
    <span class="spacer"></span>
    <span class="who">{session.username}（{isWriter ? "测量员" : "巡检员·只读"}）</span>
    <button class="secondary" on:click={refresh}>刷新</button>
    <button class="secondary" on:click={logout}>退出</button>
  {/if}
</header>

<main>
  {#if !session}
    <h1>隧道收敛测缝台</h1>
    <p class="sub">测量员提交桩号与弦长（或直填毫米），后台按当量换算成收敛后由认领线程出结论。登录框已预填可写账号 surveyor / surv123456。</p>
    <section>
      <label>用户名</label>
      <input class="field" bind:value={loginUser} autocomplete="off" />
      <label>密码</label>
      <input class="field" type="password" bind:value={loginPass} autocomplete="off" />
      <button disabled={loading} on:click={login}>登录</button>
      {#if error}<p class="err">{error}</p>{/if}
    </section>
  {:else if view === "logs"}
    {#if isWriter}
      <EntryForm {equivalent} authHeaders={headers} on:submitted={refresh} />
    {/if}
    <section>
      <h2>测量记录</h2>
      <table>
        <thead>
          <tr><th>编号</th><th>桩号</th><th>收敛mm</th><th>状态</th><th>结论</th><th>说明</th></tr>
        </thead>
        <tbody>
          {#each logs as row}
            <tr>
              <td>{row.id}</td>
              <td>{row.chainage}</td>
              <td>{row.delta_mm}</td>
              <td><span class="tag {row.status === 'pending' ? 'pending' : 'ok'}">{row.status === 'pending' ? '待处理' : '已完成'}</span></td>
              <td>
                {#if row.verdict}
                  <span class="tag {row.verdict === '合格' ? 'ok' : 'bad'}">{row.verdict}</span>
                {:else}—{/if}
              </td>
              <td>{row.reason ?? "—"}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </section>
  {:else}
    <section>
      <h2>当量参数</h2>
      {#if equivalent}
        <p class="hint">换算式：收敛(mm) = (弦长 − 基准弦长) × 当量系数；系数范围 (0, 10]，基准弦长 0 ~ 100000 mm，超限判定线 ±{equivalent.limit_mm} mm。</p>
        {#if isWriter}
          <div class="eqgrid">
            <div>
              <label>当量系数</label>
              <input class="field" bind:value={eqFactor} on:input={() => (eqEditing = true)} />
            </div>
            <div>
              <label>基准弦长（mm）</label>
              <input class="field" bind:value={eqBaseline} on:input={() => (eqEditing = true)} />
            </div>
          </div>
          <button disabled={loading} on:click={saveEquivalent}>保存当量</button>
          {#if eqError}<p class="err">{eqError}</p>{/if}
          {#if eqNotice}<p class="okmsg">{eqNotice}</p>{/if}
        {:else}
          <p>当量系数：<b>{equivalent.factor}</b>　基准弦长：<b>{equivalent.baseline_mm}</b> mm</p>
          <p class="hint">巡检员只读，不能修改当量。</p>
        {/if}
        <p class="hint">最近由 {equivalent.updated_by} 更新于 {fmt(equivalent.updated_at)}</p>
      {:else}
        <p class="hint">当量参数加载中…</p>
      {/if}
    </section>
    {#if isWriter}
      <EntryForm {equivalent} authHeaders={headers} on:submitted={refresh} />
    {/if}
    <section>
      <h2>换算流水</h2>
      <table>
        <thead>
          <tr><th>编号</th><th>桩号</th><th>方式</th><th>弦长mm</th><th>当量系数</th><th>基准弦长</th><th>收敛mm</th><th>提交人</th><th>时间</th></tr>
        </thead>
        <tbody>
          {#each conversions as c}
            <tr>
              <td>{c.id}</td>
              <td>{c.chainage ?? "—"}</td>
              <td><span class="tag {c.mode === 'chord' ? 'info' : 'plain'}">{c.mode === "chord" ? "弦长换算" : "直填毫米"}</span></td>
              <td>{c.chord_mm ?? "—"}</td>
              <td>{c.factor ?? "—"}</td>
              <td>{c.baseline_mm ?? "—"}</td>
              <td>{c.delta_mm}</td>
              <td>{c.created_by}</td>
              <td>{fmt(c.created_at)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </section>
  {/if}
</main>
