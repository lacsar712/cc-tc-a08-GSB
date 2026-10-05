<script>
  import ConversionPage from "./ConversionPage.svelte";

  let session = null;
  let logs = [];
  let loginUser = "surveyor";
  let loginPass = "surv123456";
  let error = "";
  let loading = false;
  let timer;
  let pageRefresh = null;

  let page =
    typeof window !== "undefined" && window.location.hash === "#/conversion"
      ? "conversion"
      : "logs";

  $: isWriter = session?.role === "writer";

  function headers() {
    return session ? { Authorization: "Bearer " + session.token } : {};
  }

  async function refreshLogs() {
    if (!session) return;
    const res = await fetch("/api/logs", { headers: headers() });
    if (res.status === 401) {
      logout();
      return;
    }
    if (res.ok) logs = await res.json();
  }

  async function tick() {
    await refreshLogs();
    if (pageRefresh) await pageRefresh();
  }

  function goto(p) {
    page = p;
    const hash = p === "conversion" ? "#/conversion" : "#/logs";
    if (window.location.hash !== hash) window.location.hash = hash;
  }

  function onHashChange() {
    page = window.location.hash === "#/conversion" ? "conversion" : "logs";
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
      await tick();
      timer = setInterval(tick, 2000);
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
    pageRefresh = null;
    localStorage.removeItem("tunnel_session");
  }

  function registerRefresh(fn) {
    pageRefresh = fn;
  }

  const raw = localStorage.getItem("tunnel_session");
  if (raw) {
    try {
      session = JSON.parse(raw);
      tick();
      timer = setInterval(tick, 2000);
    } catch {
      localStorage.removeItem("tunnel_session");
    }
  }
  window.addEventListener("hashchange", onHashChange);
</script>

<style>
  :global(body) {
    margin: 0;
    font-family: "Segoe UI", system-ui, sans-serif;
    background: #1c1917;
    color: #f5f5f4;
  }
  main { max-width: 1040px; margin: 0 auto; padding: 1.5rem; }
  .topbar {
    display: flex; align-items: center; justify-content: space-between;
    border-bottom: 1px solid #44403c; padding-bottom: 0.75rem; margin-bottom: 1rem;
  }
  h1 { color: #fbbf24; margin: 0; font-size: 1.35rem; }
  nav { display: flex; gap: 0.5rem; }
  nav a {
    cursor: pointer; padding: 0.35rem 0.85rem; border-radius: 6px;
    color: #d6d3d1; text-decoration: none; font-size: 0.9rem;
    border: 1px solid transparent;
  }
  nav a.active { background: #7c2d12; color: #fed7aa; border-color: #d97706; }
  .sub { color: #a8a29e; margin-bottom: 1.25rem; }
  section {
    background: #292524; border: 1px solid #44403c; border-radius: 8px;
    padding: 1rem 1.25rem; margin-bottom: 1rem;
  }
  label { display: block; font-size: 0.85rem; color: #d6d3d1; margin-bottom: 0.25rem; }
  input {
    width: 100%; box-sizing: border-box; padding: 0.5rem 0.65rem; border-radius: 6px;
    border: 1px solid #57534e; background: #0c0a09; color: #fafaf9; margin-bottom: 0.75rem;
  }
  button {
    cursor: pointer; padding: 0.5rem 1rem; border: none; border-radius: 6px;
    background: #d97706; color: #fff; font-weight: 600;
  }
  button.secondary { background: #57534e; }
  .err { color: #fb7185; }
  table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
  th, td { text-align: left; padding: 0.45rem; border-bottom: 1px solid #44403c; white-space: nowrap; }
  .tag { padding: 0.1rem 0.4rem; border-radius: 4px; font-size: 0.8rem; }
  .ok { background: #14532d; color: #86efac; }
  .bad { background: #7f1d1d; color: #fca5a5; }
  .pending { background: #713f12; color: #fde68a; }
</style>

<main>
  {#if !session}
    <h1>隧道收敛测缝台</h1>
    <p class="sub">测量员提交弦长或毫米，后台按当量换算成收敛后认领判定。登录框已预填可写账号 surveyor / surv123456。</p>
    <section>
      <label>用户名</label>
      <input bind:value={loginUser} autocomplete="off" />
      <label>密码</label>
      <input type="password" bind:value={loginPass} autocomplete="off" />
      <button disabled={loading} on:click={login}>登录</button>
      {#if error}<p class="err">{error}</p>{/if}
    </section>
  {:else}
    <div class="topbar">
      <h1>隧道收敛测缝台</h1>
      <nav>
        <a href="#/logs" class="{page === 'logs' ? 'active' : ''}" on:click={() => goto("logs")}>收敛记录</a>
        <a href="#/conversion" class="{page === 'conversion' ? 'active' : ''}" on:click={() => goto("conversion")}>当量换算</a>
      </nav>
      <div>
        <span class="sub" style="margin:0 0.75rem 0 0;">{session.username}（{isWriter ? "测量员" : "巡检员"}）</span>
        <button class="secondary" on:click={logout}>退出</button>
      </div>
    </div>

    {#if page === "conversion"}
      <ConversionPage {session} {registerRefresh} />
    {:else}
      <section>
        <table>
          <thead>
            <tr>
              <th>编号</th><th>桩号</th><th>来路</th><th>弦长mm</th><th>当量</th>
              <th>收敛mm</th><th>状态</th><th>结论</th><th>说明</th>
            </tr>
          </thead>
          <tbody>
            {#each logs as row}
              <tr>
                <td>{row.id}</td>
                <td>{row.chainage}</td>
                <td>{row.input_mode === "chord" ? "弦长路" : "毫米路"}</td>
                <td>{row.chord_mm ?? "—"}</td>
                <td>{row.coefficient ?? "—"}</td>
                <td>{row.delta_mm}</td>
                <td><span class="tag {row.status === 'pending' ? 'pending' : 'ok'}">{row.status === 'pending' ? '待处理' : '已完成'}</span></td>
                <td>
                  {#if row.verdict}
                    <span class="tag {row.verdict === '合格' ? 'ok' : 'bad'}">{row.verdict}</span>
                  {:else}—{/if}
                </td>
                <td style="white-space:normal;">{row.reason ?? "—"}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </section>
    {/if}
  {/if}
</main>
