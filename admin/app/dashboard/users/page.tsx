"use client";

import { useEffect, useState, useCallback } from "react";
import { api, UserRow, UsersListResponse, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

const STATUS_LABEL: Record<string, string> = {
  pending: "승인 대기",
  active: "활성",
  expired: "만료",
  suspended: "정지",
  rejected: "거부",
};

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  pending: "outline",
  active: "default",
  expired: "secondary",
  suspended: "destructive",
  rejected: "destructive",
};

export default function UsersPage() {
  const [data, setData] = useState<UsersListResponse | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    try {
      const res = await api.listUsers({
        status: statusFilter || undefined,
        q: search || undefined,
        limit: 200,
      });
      setData(res);
    } catch (e) {
      if (e instanceof ApiError) alert(e.message);
    }
  }, [statusFilter, search]);

  useEffect(() => {
    load();
  }, [load]);

  async function changeStatus(user: UserRow, status: string) {
    const note = prompt(`'${user.email}' → ${STATUS_LABEL[status]}\n관리자 메모 (선택):`);
    if (note === null) return; // 취소
    try {
      await api.changeUserStatus(user.id, status, note);
      await load();
    } catch (e) {
      if (e instanceof ApiError) alert(e.message);
    }
  }

  async function deleteUser(user: UserRow) {
    if (!confirm(`'${user.email}' 사용자를 완전히 삭제합니까?\n(연락처/템플릿/발송로그도 삭제됩니다)`)) return;
    try {
      await api.deleteUser(user.id);
      await load();
    } catch (e) {
      if (e instanceof ApiError) alert(e.message);
    }
  }

  if (!data) return <div className="text-slate-500">로딩 중...</div>;

  const tabs = [
    { value: "", label: "전체", count: data.total },
    { value: "pending", label: "승인 대기", count: data.pending },
    { value: "active", label: "활성", count: data.active },
    { value: "expired", label: "만료", count: data.expired },
    { value: "suspended", label: "정지", count: data.suspended },
    { value: "rejected", label: "거부", count: data.rejected },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">사용자 관리</h1>

      <Tabs value={statusFilter} onValueChange={setStatusFilter}>
        <TabsList>
          {tabs.map((t) => (
            <TabsTrigger key={t.value} value={t.value}>
              {t.label}
              <Badge variant="secondary" className="ml-2">
                {t.count}
              </Badge>
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <div className="flex gap-2">
        <Input
          placeholder="이메일 검색..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs"
        />
      </div>

      <div className="rounded-md border bg-white">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>이메일</TableHead>
              <TableHead>상태</TableHead>
              <TableHead>라이선스</TableHead>
              <TableHead className="text-right">디바이스</TableHead>
              <TableHead className="text-right">30일 발송</TableHead>
              <TableHead>가입일</TableHead>
              <TableHead>마지막 로그인</TableHead>
              <TableHead className="w-[100px]">작업</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.users.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="h-24 text-center text-slate-400">
                  사용자 없음
                </TableCell>
              </TableRow>
            ) : (
              data.users.map((u) => (
                <TableRow key={u.id}>
                  <TableCell className="font-medium">
                    {u.email}
                    {u.is_admin && (
                      <Badge variant="default" className="ml-2 bg-purple-600">
                        ADMIN
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge variant={STATUS_VARIANT[u.status]}>
                      {STATUS_LABEL[u.status] || u.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-mono text-xs">{u.license_key}</TableCell>
                  <TableCell className="text-right">{u.device_count}</TableCell>
                  <TableCell className="text-right">{u.send_count_30d}</TableCell>
                  <TableCell className="text-xs">
                    {new Date(u.created_at).toLocaleDateString("ko-KR")}
                  </TableCell>
                  <TableCell className="text-xs">
                    {u.last_login_at
                      ? new Date(u.last_login_at).toLocaleString("ko-KR")
                      : "-"}
                  </TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger className="inline-flex h-8 items-center rounded-md border bg-white px-3 text-sm hover:bg-slate-50">
                        작업 ▾
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        {u.status !== "active" && (
                          <DropdownMenuItem onClick={() => changeStatus(u, "active")}>
                            ✓ 활성화 (승인)
                          </DropdownMenuItem>
                        )}
                        {u.status !== "suspended" && (
                          <DropdownMenuItem onClick={() => changeStatus(u, "suspended")}>
                            ⏸ 정지 (킬 스위치)
                          </DropdownMenuItem>
                        )}
                        {u.status === "pending" && (
                          <DropdownMenuItem onClick={() => changeStatus(u, "rejected")}>
                            ✕ 가입 거부
                          </DropdownMenuItem>
                        )}
                        {u.status !== "expired" && (
                          <DropdownMenuItem onClick={() => changeStatus(u, "expired")}>
                            ⌛ 만료 처리
                          </DropdownMenuItem>
                        )}
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          className="text-red-600"
                          onClick={() => deleteUser(u)}
                        >
                          🗑 완전 삭제
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
