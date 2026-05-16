"use client";

import { useEffect, useState } from "react";
import { api, StatsResponse } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  CartesianGrid,
} from "recharts";

export default function StatsPage() {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [days, setDays] = useState(30);

  useEffect(() => {
    api.getStats(days).then(setStats).catch(console.error);
  }, [days]);

  if (!stats) return <div className="text-slate-500">로딩 중...</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">대시보드</h1>
        <select
          className="rounded-md border bg-white px-3 py-1.5 text-sm"
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
        >
          <option value={7}>최근 7일</option>
          <option value={30}>최근 30일</option>
          <option value={90}>최근 90일</option>
        </select>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardDescription>전체 사용자</CardDescription>
            <CardTitle className="text-4xl">{stats.total_users}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>활성 사용자</CardDescription>
            <CardTitle className="text-4xl text-emerald-600">
              {stats.active_users}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>승인 대기</CardDescription>
            <CardTitle className="text-4xl text-amber-600">
              {stats.pending_users}
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>일별 발송량</CardTitle>
            <CardDescription>최근 {days}일</CardDescription>
          </CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={stats.daily_sends}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="count"
                  stroke="#0ea5e9"
                  strokeWidth={2}
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>일별 가입자</CardTitle>
            <CardDescription>최근 {days}일</CardDescription>
          </CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={stats.daily_signups}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip />
                <Bar dataKey="count" fill="#10b981" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>발송량 상위 사용자</CardTitle>
          <CardDescription>최근 {days}일 누적</CardDescription>
        </CardHeader>
        <CardContent>
          {stats.top_users.length === 0 ? (
            <p className="text-sm text-slate-500">발송 기록 없음</p>
          ) : (
            <ul className="space-y-2">
              {stats.top_users.map((u, i) => (
                <li
                  key={u.email}
                  className="flex items-center justify-between border-b py-2 text-sm last:border-0"
                >
                  <span>
                    <span className="mr-2 font-mono text-slate-400">
                      #{i + 1}
                    </span>
                    {u.email}
                  </span>
                  <span className="font-mono font-bold">{u.count}</span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
