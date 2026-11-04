package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestCategoryOf(t *testing.T) {
	cases := map[string]string{
		"report.PDF": "documents", "photo.jpeg": "images", "clip.mkv": "video",
		"backup.tar.gz": "archives", "noext": "other", "script.sh": "other",
	}
	for name, want := range cases {
		if got := categoryOf(name); got != want {
			t.Errorf("categoryOf(%q) = %q, want %q", name, got, want)
		}
	}
}

func TestSortDryRunChangesNothing(t *testing.T) {
	dir := t.TempDir()
	for _, f := range []string{"a.pdf", "b.png"} {
		if err := os.WriteFile(filepath.Join(dir, f), []byte("x"), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	if code := cmdSort([]string{"--dry-run", dir}); code != exitOK {
		t.Fatalf("exit %d", code)
	}
	if _, err := os.Stat(filepath.Join(dir, "a.pdf")); err != nil {
		t.Fatal("dry-run перемістив файл")
	}
	if _, err := os.Stat(filepath.Join(dir, "documents")); err == nil {
		t.Fatal("dry-run створив теку")
	}
}

func TestSortMovesAndKeepsExisting(t *testing.T) {
	dir := t.TempDir()
	if err := os.MkdirAll(filepath.Join(dir, "images"), 0o755); err != nil {
		t.Fatal(err)
	}
	for _, f := range []string{"a.pdf", "b.png", filepath.Join("images", "b.png")} {
		if err := os.WriteFile(filepath.Join(dir, f), []byte(f), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	if code := cmdSort([]string{dir}); code != exitOK {
		t.Fatalf("exit %d", code)
	}
	for _, f := range []string{"documents/a.pdf", "images/b.png", "images/b (1).png"} {
		if _, err := os.Stat(filepath.Join(dir, f)); err != nil {
			t.Errorf("немає %s", f)
		}
	}
}

func TestUsageErrors(t *testing.T) {
	if code := run([]string{"sort"}); code != exitUsage {
		t.Errorf("sort без теки: exit %d", code)
	}
	if code := run([]string{"stats", "/no/such/dir"}); code != exitUsage {
		t.Errorf("stats неіснуючої теки: exit %d", code)
	}
	if code := run([]string{"bogus"}); code != exitUsage {
		t.Errorf("невідома підкоманда: exit %d", code)
	}
}
