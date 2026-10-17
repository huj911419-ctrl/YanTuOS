import { expect, test } from "@playwright/test";

test("daily task can be created, edited, completed, filtered, and deleted", async ({
  page,
  request,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const name = `真实任务-${testInfo.project.name}`;
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("把今天");
  await page.getByRole("button", { name: "新建学习任务", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("任务名称").fill(name);
  await dialog.getByLabel("学习目标或备注").fill("独立完成五道基础题");
  await dialog.getByRole("button", { name: "保存任务" }).click();
  await expect(dialog).not.toBeVisible();
  await page.getByRole("button", { name: "每日计划", exact: true }).click();
  await expect(page.getByText(name, { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: `编辑任务：${name}`, exact: true })
    .click();
  await dialog.getByLabel("任务名称").fill(`${name}-已编辑`);
  await dialog.getByRole("button", { name: "保存任务" }).click();
  await expect(dialog).not.toBeVisible();
  await page
    .getByRole("button", { name: `完成任务：${name}-已编辑`, exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: `取消完成：${name}-已编辑` }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "后一天", exact: true }).click();
  await expect(
    page.getByText(`${name}-已编辑`, { exact: true }),
  ).not.toBeVisible();
  await page.getByRole("button", { name: "今天", exact: true }).click();
  await expect(page.getByText(`${name}-已编辑`, { exact: true })).toBeVisible();
  page.once("dialog", (d) => d.accept());
  await page
    .getByRole("button", { name: `删除任务：${name}-已编辑`, exact: true })
    .click();
  await expect(
    page.getByText(`${name}-已编辑`, { exact: true }),
  ).not.toBeVisible();
  const tasks = await (await request.get("/api/tasks")).json();
  expect(
    tasks.some((t: { title: string }) => t.title === `${name}-已编辑`),
  ).toBe(false);
  expect(errors).toEqual([]);
});

test("timer survives refresh, excludes paused time, and creates real history", async ({
  page,
  request,
}, testInfo) => {
  const topic = `浏览器验收：基础极限-${testInfo.project.name}`;
  const note = `测试记录在临时数据库-${testInfo.project.name}`;
  await page.goto("/#focus");
  await page.getByLabel("学习科目", { exact: true }).fill("数学");
  await page.getByLabel("本次学习内容").fill(topic);
  await page.getByRole("button", { name: "开始学习", exact: true }).click();
  await expect(page.getByText("正在专注", { exact: true })).toBeVisible();
  await expect
    .poll(
      async () =>
        (await (await request.get("/api/sessions/current")).json())
          .elapsed_seconds,
    )
    .toBeGreaterThanOrEqual(1);
  await page.reload();
  await expect(page.getByText(topic, { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "暂停学习", exact: true }).click();
  await expect(page.getByText("已暂停 · 休息一下")).toBeVisible();
  const before = await (await request.get("/api/sessions/current")).json();
  await page.reload();
  await expect(page.getByText("已暂停 · 休息一下")).toBeVisible();
  const after = await (await request.get("/api/sessions/current")).json();
  expect(after.elapsed_seconds).toBe(before.elapsed_seconds);
  await page.getByRole("button", { name: "继续学习", exact: true }).click();
  await expect(page.getByText("正在专注", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "结束并记录", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("学习小结（选填）").fill(note);
  await dialog.getByRole("button", { name: "确认结束并保存" }).click();
  await expect(dialog).not.toBeVisible();
  await expect(page.getByText(note, { exact: true })).toBeVisible();
  expect(await (await request.get("/api/sessions/current")).json()).toBeNull();
  const stats = await (await request.get("/api/stats")).json();
  expect(stats.today_seconds).toBeGreaterThanOrEqual(1);
  expect(
    stats.subjects.some((s: { subject: string }) => s.subject === "数学"),
  ).toBe(true);
});

test("knowledge, manual mistakes, automatic review schedule, AI status and downloads", async ({
  page,
  request,
}, testInfo) => {
  const point = `浏览器知识点-${testInfo.project.name}`;
  const title = `错题-${testInfo.project.name}`;
  await page.goto("/#knowledge");
  await expect(page.getByText("不是某类考研数学的最终大纲")).toBeVisible();
  await page.getByRole("button", { name: "添加知识点", exact: true }).click();
  let dialog = page.getByRole("dialog");
  await dialog.getByLabel("知识点名称").fill(point);
  await dialog.getByLabel("知识分类").fill("自定义基础");
  await dialog.getByRole("button", { name: "保存知识点" }).click();
  await expect(dialog).not.toBeVisible();
  await page
    .getByRole("combobox", { name: `${point}的学习状态`, exact: true })
    .selectOption("learning");
  await expect(
    page.getByRole("combobox", { name: `${point}的学习状态`, exact: true }),
  ).toHaveValue("learning");
  await page.getByRole("button", { name: "我的错题", exact: true }).click();
  await page.getByRole("button", { name: "录入错题", exact: true }).click();
  dialog = page.getByRole("dialog");
  await dialog.getByLabel("错题标题").fill(title);
  await dialog.getByLabel("题目内容").fill("求函数 f(x)=x² 的导数。");
  await dialog
    .getByLabel("正确答案与解题过程")
    .fill("使用幂函数求导法则，答案为 2x。");
  await dialog.getByLabel("错误原因", { exact: true }).fill("混淆求导和积分");
  await dialog.getByRole("checkbox", { name: new RegExp(point) }).check();
  await dialog.getByRole("button", { name: "保存错题" }).click();
  await expect(dialog).not.toBeVisible();
  await page.getByLabel("按知识点筛选错题").selectOption({ label: point });
  await expect(
    page.getByRole("heading", { name: title, exact: true }),
  ).toBeVisible();
  const mistakes = await (await request.get("/api/mistakes")).json();
  const saved = mistakes.find((m: { title: string }) => m.title === title);
  expect(saved.knowledge_ids.length).toBe(1);
  expect(saved.review.due_date).toBeTruthy();
  await page.getByRole("button", { name: "复习日程", exact: true }).click();
  await page.getByRole("button", { name: /全部待复习/ }).click();
  await expect(page.getByText(title, { exact: true })).toBeVisible();
  const row = page.locator(".review-row").filter({ hasText: title });
  await row.getByRole("button", { name: "查看题目" }).click();
  dialog = page.getByRole("dialog");
  await expect(
    dialog.getByText("求函数 f(x)=x² 的导数。", { exact: true }),
  ).toBeVisible();
  await expect(
    dialog.getByText("混淆求导和积分", { exact: true }),
  ).not.toBeVisible();
  await dialog.getByRole("button", { name: "查看答案与错因" }).click();
  await expect(
    dialog.getByText("混淆求导和积分", { exact: true }),
  ).toBeVisible();
  await dialog.getByRole("button", { name: "关闭弹窗" }).click();
  await page.getByRole("button", { name: "数据与设置", exact: true }).click();
  await expect(page.getByText(/尚未接入真实 AI 服务/)).toBeVisible();
  const [jsonFile] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "导出 JSON" }).click(),
  ]);
  expect(jsonFile.suggestedFilename()).toMatch(/\.json$/);
  await expect(
    page.getByRole("button", { name: "下载完整备份" }),
  ).toBeEnabled();
  const [sqliteFile] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "下载完整备份" }).click(),
  ]);
  expect(sqliteFile.suggestedFilename()).toMatch(/\.zip$/);
  expect((await request.get("/api/ai/status")).ok()).toBe(true);
  await request.delete(`/api/mistakes/${saved.id}`);
  await request.delete(`/api/knowledge/${saved.knowledge_ids[0]}`);
});

test("due reviews save remembered and forgotten outcomes with history", async ({
  page,
  request,
}, testInfo) => {
  await page.goto("/#reviews");
  for (const outcome of ["remembered", "forgotten"]) {
    const title = `E2E到期样本-${testInfo.project.name}-${outcome}`;
    const row = page.locator(".review-row").filter({ hasText: title });
    await row.getByRole("button", { name: "开始复习" }).click();
    const dialog = page.getByRole("dialog");
    await expect(
      dialog.getByRole("button", { name: "本次已记住" }),
    ).toBeDisabled();
    await dialog.getByRole("button", { name: "查看答案与错因" }).click();
    await dialog.getByLabel("本次复习笔记（选填）").fill("独立重做后确认");
    await dialog
      .getByRole("button", {
        name: outcome === "remembered" ? "本次已记住" : "还没掌握",
        exact: true,
      })
      .click();
    await expect(dialog).not.toBeVisible();
    await expect(row).not.toBeVisible();
    const all = await (await request.get("/api/mistakes")).json();
    const saved = all.find((m: { title: string }) => m.title === title);
    expect(saved.review.stage).toBe(outcome === "remembered" ? 1 : 0);
    const history = await (
      await request.get(`/api/mistakes/${saved.id}/reviews`)
    ).json();
    expect(history.length).toBe(1);
    expect(history[0].outcome).toBe(outcome);
    expect(history[0].notes).toBe("独立重做后确认");
  }
});

test("save conflicts remain visible inside the open form", async ({ page }) => {
  await page.goto("/#knowledge");
  await page.getByRole("button", { name: "添加知识点", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("知识点名称").fill("代数运算与因式分解");
  await dialog.getByLabel("知识分类").fill("基础工具");
  await dialog.getByRole("button", { name: "保存知识点" }).click();
  await expect(dialog.getByRole("alert")).toContainText("不能重复");
  await expect(dialog.getByLabel("知识点名称")).toHaveValue(
    "代数运算与因式分解",
  );
  await dialog.getByRole("button", { name: "取消", exact: true }).click();
  await expect(dialog).not.toBeVisible();
});

test("all screens fit the viewport", async ({ page }, testInfo) => {
  for (const hash of [
    "overview",
    "tasks",
    "focus",
    "knowledge",
    "mistakes",
    "reviews",
    "settings",
  ]) {
    await page.goto(`/#${hash}`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth + 1,
      ),
    ).toBe(true);
  }
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("把今天");
  await page.screenshot({
    path: `test-results/overview-${testInfo.project.name}.png`,
    fullPage: true,
  });
});
