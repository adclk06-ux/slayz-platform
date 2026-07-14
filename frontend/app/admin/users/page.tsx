"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AuthUser,
  createAdminUser,
  fetchAdminUsers,
  updateAdminUser,
} from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";
import { ArrowLeft, KeyRound, Plus, ShieldCheck, UserCheck, UserX } from "lucide-react";

const EMPTY_FORM = { full_name: "", email: "", password: "", role: "viewer" };

export default function AdminUsersPage() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const activeCount = useMemo(() => users.filter((item) => item.is_active).length, [users]);

  useEffect(() => {
    if (loading) return;
    if (!user || user.role !== "admin") {
      router.replace("/");
      return;
    }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, user?.id]);

  async function reload() {
    try {
      setError(null);
      setUsers(await fetchAdminUsers());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kullanıcılar yüklenemedi.");
    }
  }

  async function createUser(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const email = form.email.includes("@") ? form.email : `${form.email}@slayz.com`;
      await createAdminUser({ ...form, email: email.trim().toLowerCase() });
      setForm(EMPTY_FORM);
      setNotice("Kullanıcı oluşturuldu ve artık sohbet listesinde görünecek.");
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kullanıcı oluşturulamadı.");
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(item: AuthUser) {
    try {
      setError(null);
      await updateAdminUser(item.id, { is_active: !item.is_active });
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kullanıcı durumu değiştirilemedi.");
    }
  }

  async function resetPassword(item: AuthUser) {
    const password = window.prompt(`${item.full_name} için yeni şifre (en az 8 karakter):`);
    if (!password) return;
    try {
      setError(null);
      await updateAdminUser(item.id, { password });
      setNotice(`${item.full_name} kullanıcısının şifresi güncellendi.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Şifre güncellenemedi.");
    }
  }

  if (loading || !user || user.role !== "admin") {
    return <div className="min-h-screen grid place-items-center text-sm text-slate-400">Yetki kontrol ediliyor...</div>;
  }

  return (
    <main className="min-h-screen bg-slate-50 px-5 py-8">
      <div className="mx-auto max-w-5xl space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <button onClick={() => router.push("/")} className="rounded-xl border border-slate-200 bg-white p-2 hover:bg-slate-100" aria-label="Ana sayfa"><ArrowLeft className="h-4 w-4" /></button>
            <div><h1 className="text-xl font-bold text-slate-900">Kullanıcı Yönetimi</h1><p className="text-sm text-slate-500">{activeCount} aktif kullanıcı · yalnızca @slayz.com</p></div>
          </div>
          <span className="inline-flex items-center gap-2 rounded-full bg-indigo-50 px-3 py-1.5 text-xs font-semibold text-indigo-700"><ShieldCheck className="h-4 w-4" /> Yönetici: {user.full_name}</span>
        </div>

        {(error || notice) && <div className={`rounded-xl border p-3 text-sm ${error ? "border-rose-200 bg-rose-50 text-rose-700" : "border-emerald-200 bg-emerald-50 text-emerald-700"}`}>{error || notice}</div>}

        <form onSubmit={createUser} className="grid gap-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm md:grid-cols-2">
          <div className="md:col-span-2 flex items-center gap-2 font-bold text-slate-900"><Plus className="h-4 w-4 text-indigo-600" /> Yeni kullanıcı ekle</div>
          <input required minLength={2} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} placeholder="Ad soyad" className="rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm outline-none focus:border-indigo-500" />
          <div className="flex rounded-xl border border-slate-200 bg-white focus-within:border-indigo-500"><input required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value.replace(/@slayz\.com$/i, "") })} placeholder="osman" className="min-w-0 flex-1 rounded-l-xl px-3.5 py-2.5 text-sm outline-none" /><span className="flex items-center border-l border-slate-100 px-3 text-sm text-slate-400">@slayz.com</span></div>
          <input required minLength={8} type="password" autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder="Geçici şifre (en az 8 karakter)" className="rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm outline-none focus:border-indigo-500" />
          <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} className="rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm outline-none focus:border-indigo-500"><option value="viewer">Kullanıcı</option><option value="analyst">Analist / Editör</option><option value="admin">Yönetici</option></select>
          <button disabled={saving} className="md:col-span-2 rounded-xl bg-indigo-600 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50">{saving ? "Ekleniyor..." : "Kullanıcıyı Ekle"}</button>
        </form>

        <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-100 px-5 py-4 font-bold text-slate-900">Kayıtlı kullanıcılar</div>
          <div className="divide-y divide-slate-100">
            {users.map((item) => (
              <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
                <div className="min-w-0"><div className="flex items-center gap-2"><span className="truncate font-semibold text-slate-900">{item.full_name}</span><span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${item.is_active ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>{item.is_active ? "AKTİF" : "PASİF"}</span></div><div className="truncate text-xs text-slate-500">{item.email} · {item.role}</div></div>
                <div className="flex items-center gap-2">
                  <button onClick={() => resetPassword(item)} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50"><KeyRound className="h-3.5 w-3.5" /> Şifre</button>
                  <button disabled={item.id === user.id} onClick={() => toggleActive(item)} className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-2 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-40 ${item.is_active ? "bg-rose-50 text-rose-700 hover:bg-rose-100" : "bg-emerald-50 text-emerald-700 hover:bg-emerald-100"}`}>{item.is_active ? <UserX className="h-3.5 w-3.5" /> : <UserCheck className="h-3.5 w-3.5" />}{item.is_active ? "Pasifleştir" : "Etkinleştir"}</button>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
