import { expect, test } from "@playwright/test";

test("V2 goal, priority task, manual record, statistics and knowledge review", async ({
  page,
  request,
}, info) => {
  const suffix = info.project.name;
  await page.goto("/#plans");
  await page.getByRole("button", { name: "新建目标", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("目标名称").fill("独立练习-" + suffix);
  await dialog.getByLabel("验收说明").fill("独立做出五道题");
  await dialog.getByRole("button", { name: "保存目标", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  await expect(
    page.getByText("独立练习-" + suffix, { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "创建学习任务", exact: true }).click();
  await dialog.getByLabel("任务名称").fill("周任务-" + suffix);
  await dialog.getByLabel("任务优先级").selectOption("1");
  await dialog
    .getByLabel("关联阶段目标")
    .selectOption({ label: "独立练习-" + suffix });
  await dialog.getByRole("button", { name: "保存任务" }).click();
  await expect(dialog).not.toBeVisible();
  await page.reload();
  await expect(
    page.getByText("周任务-" + suffix, { exact: true }),
  ).toBeVisible();
  await page.goto("/#focus");
  await page.getByRole("button", { name: "补录学习记录", exact: true }).click();
  await dialog.getByLabel("记录内容").fill("补录-" + suffix);
  await dialog
    .getByLabel("开始时间（北京时间）")
    .fill(suffix.includes("webkit") ? "2026-01-02T08:00" : "2026-01-01T08:00");
  await dialog.getByLabel("学习分钟数").fill("45");
  await dialog.getByRole("button", { name: "保存学习记录" }).click();
  await expect(dialog).not.toBeVisible();
  await page.goto("/#analytics");
  await page.getByLabel("开始日期", { exact: true }).fill("2026-01-01");
  await page.getByLabel("结束日期", { exact: true }).fill("2026-01-02");
  await expect(
    page.getByRole("heading", { name: "学习趋势与日历" }),
  ).toBeVisible();
  const stats = await (
    await request.get("/api/analytics?start=2026-01-01&end=2026-01-02")
  ).json();
  expect(stats.seconds).toBeGreaterThanOrEqual(2700);
  const k = await (
    await request.post("/api/knowledge", {
      data: {
        title: "V2知识-" + suffix,
        domain: "测试章节",
        status: "learning",
        mastery: 1,
      },
    })
  ).json();
  const today = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
  }).format(new Date());
  await request.put(`/api/review-schedule/knowledge/${k.id}`, {
    data: { due_date: today },
  });
  await page.goto("/#reviews");
  await page
    .locator(".v2-row")
    .filter({ hasText: k.title })
    .getByRole("button", { name: "回顾知识点" })
    .click();
  await dialog.getByRole("button", { name: "独立完成", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  expect(
    (await (await request.get("/api/knowledge")).json()).find(
      (x: { id: number }) => x.id === k.id,
    ).mastery,
  ).toBe(2);
});

test("new pages fit mobile viewport and have no runtime errors", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  for (const name of ["plans", "analytics", "reviews"]) {
    await page.goto("/#" + name);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.getByText("正在读取…")).toHaveCount(0);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth + 1,
      ),
    ).toBe(true);
  }
  expect(errors).toEqual([]);
});

test("materials, image mistake, AI disabled and complete archive", async ({
  page,
}, info) => {
  await page.goto("/#materials");
  await page.getByRole("button", { name: "添加资料或笔记" }).click();
  const d = page.getByRole("dialog");
  await d.getByLabel("资料名称").fill("资料-" + info.project.name);
  await d.getByLabel("上传资料文件").setInputFiles({
    name: "notes.md",
    mimeType: "text/plain",
    buffer: Buffer.from("# 基础概念\n我的理解"),
  });
  await expect(d.getByRole("button", { name: "保存资料" })).toBeEnabled();
  await d.getByLabel("个人笔记").fill("独立整理的知识");
  await d.getByRole("button", { name: "保存资料" }).click();
  await expect(d).not.toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "资料-" + info.project.name }),
  ).toBeVisible();
  await page.goto("/#mistakes");
  await page.getByRole("button", { name: "录入错题", exact: true }).click();
  await d.getByLabel("错题标题").fill("图片错题-" + info.project.name);
  await d.getByLabel("题目内容").fill("题目见图");
  await d.getByLabel("上传题目图片").setInputFiles("public/pwa-192.png");
  await expect(d.getByAltText("题目图片 1")).toBeVisible();
  await d.getByLabel("我的错误答案").fill("需要检查符号");
  await d.getByRole("button", { name: "保存错题" }).click();
  await expect(d).not.toBeVisible();
  await page.reload();
  const card = page
    .locator(".mistake-card")
    .filter({ hasText: "图片错题-" + info.project.name });
  await card.getByRole("button", { name: "查看", exact: true }).click();
  await expect(d.getByAltText("题目图片 1")).toBeVisible();
  await d.getByRole("button", { name: "关闭弹窗" }).click();
  await page.goto("/#ai");
  await expect(
    page.getByRole("button", { name: "预览发送内容" }),
  ).toBeDisabled();
  await page.getByLabel("待核对算式").fill("(2+3)*4=20");
  await page.getByRole("button", { name: "核对算式", exact: true }).click();
  await expect(page.getByText(/两侧数值一致/)).toBeVisible();
  for (const hash of ["ai", "materials", "settings"]) {
    await page.goto("/#" + hash);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth + 1,
      ),
    ).toBe(true);
  }
  await page.getByRole("button", { name: "检查数据完整性" }).click();
  await expect(page.getByText("数据库 ok，附件 ok")).toBeVisible();
  const [backup] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "下载完整备份", exact: true }).click(),
  ]);
  expect(backup.suggestedFilename()).toMatch(/\.zip$/);
});

test("PWA manifest and offline fallback exclude personal API cache", async ({
  page,
  context,
}, info) => {
  test.skip(
    info.project.name !== "desktop-chromium",
    "Service Worker 离线自动化在 Chromium 验证；iPhone 安装需真机。",
  );
  await page.goto("/");
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
  });
  await expect
    .poll(() => page.evaluate(() => !!navigator.serviceWorker.controller))
    .toBe(true);
  const manifest = await (
    await page.request.get("/manifest.webmanifest")
  ).json();
  expect(manifest.display).toBe("standalone");
  await context.setOffline(true);
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "你的学习空间暂时离线" }),
  ).toBeVisible();
  const cached = await page.evaluate(async () => {
    const keys = await caches.keys();
    return (
      await Promise.all(
        keys.map(async (k) =>
          (await (await caches.open(k)).keys()).map((x) => x.url),
        ),
      )
    ).flat();
  });
  expect(cached.some((x) => x.includes("/api/"))).toBe(false);
  await context.setOffline(false);
});
