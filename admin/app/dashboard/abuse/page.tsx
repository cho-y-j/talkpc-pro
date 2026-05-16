"use client";

import { useEffect, useState, useCallback } from "react";
import { api, AbuseRow, ApiError } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export default function AbusePage() {
  const [rows, setRows] = useState<AbuseRow[]>([]);
  const [days, setDays] = useState(1);
  const [threshold, setThreshold] = useState(100);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.detectAbuse(days, threshold);
      setRows(res);
    } catch (e) {
      if (e instanceof ApiError) alert(e.message);
    } finally {
      setLoading(false);
    }
  }, [days, threshold]);

  useEffect(() => {
    load();
  }, [load]);

  async function suspend(row: AbuseRow) {
    const note = prompt(`'${row.email}' 정지 사유:`,
                          `과도한 발송 (${row.count}건/${row.period_days}일)`);
    if (note === null) return;
    try {
      await api.changeUserStatus(row.user_id, "suspended", note);
      await load();
    } catch (e) {
      if (e instanceof ApiError) alert(e.message);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">부정 사용 감지</h1>

      <Card>
        <CardHeader>
          <CardTitle>필터</CardTitle>
          <CardDescription>최근 N일간 임계치 이상 발송한 사용자</CardDescription>
        </CardHeader>
        <CardContent className="flex items-center gap-4">
          <label className="text-sm">
            기간:
            <select
              className="ml-2 rounded-md border bg-white px-2 py-1 text-sm"
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
            >
              <option value={1}>1일</option>
              <option value={7}>7일</option>
              <option value={30}>30일</option>
            </select>
          </label>
          <label className="text-sm">
            임계치 ≥
            <input
              type="number"
              className="ml-2 w-24 rounded-md border bg-white px-2 py-1 text-sm"
              value={threshold}
              onChange={(e) => setThreshold(Number(e.target.value))}
            />
            건
          </label>
          <Button onClick={load} disabled={loading} variant="outline" size="sm">
            {loading ? "조회중..." : "새로고침"}
          </Button>
        </CardContent>
      </Card>

      {rows.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-slate-500">
            의심 사용자 없음
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {rows.map((r) => (
            <Card key={r.user_id}>
              <CardContent className="flex items-center justify-between py-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{r.email}</span>
                    <Badge
                      variant={r.status === "suspended" ? "destructive" : "outline"}
                    >
                      {r.status}
                    </Badge>
                  </div>
                  <div className="mt-1 text-sm text-slate-500">
                    {r.period_days}일간{" "}
                    <span className="font-bold text-red-600">{r.count}건</span> 발송
                  </div>
                </div>
                {r.status !== "suspended" && (
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => suspend(r)}
                  >
                    정지 처리
                  </Button>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
