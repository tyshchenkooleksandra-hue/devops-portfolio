// fsort — розкладає файли теки за типами: документи, зображення, відео, архіви.
//
//	fsort sort  [--dry-run] [--dest <тека>] <тека>
//	fsort stats <тека>
package main

import (
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

const version = "1.0.0"

// Коди виходу.
const (
	exitOK    = 0
	exitError = 1 // помилка під час роботи (не вдалося перемістити файл)
	exitUsage = 2 // неправильні параметри / тека не існує
)

var categories = map[string][]string{
	"documents": {".pdf", ".doc", ".docx", ".odt", ".txt", ".md", ".rtf", ".xls", ".xlsx", ".ppt", ".pptx", ".csv"},
	"images":    {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".heic", ".tiff"},
	"video":     {".mp4", ".mkv", ".avi", ".mov", ".webm", ".wmv", ".flv"},
	"archives":  {".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar"},
}

const other = "other"

var byExt = func() map[string]string {
	m := map[string]string{}
	for cat, exts := range categories {
		for _, e := range exts {
			m[e] = cat
		}
	}
	return m
}()

func categoryOf(name string) string {
	lower := strings.ToLower(name)
	// .tar.gz — подвійне розширення, але Ext поверне лише .gz; обидва ведуть в archives.
	if c, ok := byExt[filepath.Ext(lower)]; ok {
		return c
	}
	return other
}

func usage(w io.Writer) {
	fmt.Fprintf(w, `fsort %s — розкладає файли теки в підтеки за типами.

Використання:
  fsort sort  [--dry-run] [--dest <тека>] <тека>   розкласти файли (лише верхній рівень теки)
  fsort stats <тека>                              порахувати файли за категоріями
  fsort version | help

Категорії: documents, images, video, archives, other (усе інше).
Наявний файл із тим самим ім'ям не перезаписується — до нового додається « (1)», « (2)»…

Коди виходу: 0 — успіх, 1 — помилка під час переміщення, 2 — неправильні параметри.

Приклад:
  fsort sort --dry-run ~/Downloads
  fsort sort --dest ~/Sorted ~/Downloads
  fsort stats ~/Downloads
`, version)
}

// listFiles повертає звичайні файли верхнього рівня, відсортовані за іменем.
func listFiles(dir string) ([]string, error) {
	info, err := os.Stat(dir)
	if err != nil {
		return nil, fmt.Errorf("тека не існує: %s", dir)
	}
	if !info.IsDir() {
		return nil, fmt.Errorf("не є текою: %s", dir)
	}
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, fmt.Errorf("не вдалося прочитати %s: %w", dir, err)
	}
	var files []string
	for _, e := range entries {
		if e.Type().IsRegular() {
			files = append(files, e.Name())
		}
	}
	sort.Strings(files)
	return files, nil
}

// freeName знаходить ім'я, яке ще не зайняте в теці dest.
func freeName(dest, name string) string {
	candidate := filepath.Join(dest, name)
	ext := filepath.Ext(name)
	base := strings.TrimSuffix(name, ext)
	for i := 1; ; i++ {
		if _, err := os.Lstat(candidate); errors.Is(err, os.ErrNotExist) {
			return candidate
		}
		candidate = filepath.Join(dest, fmt.Sprintf("%s (%d)%s", base, i, ext))
	}
}

func cmdSort(args []string) int {
	fs := flag.NewFlagSet("sort", flag.ContinueOnError)
	fs.SetOutput(os.Stderr)
	dryRun := fs.Bool("dry-run", false, "показати, що буде зроблено, нічого не змінюючи")
	dest := fs.String("dest", "", "куди складати підтеки (типово — сама тека)")
	fs.Usage = func() { usage(os.Stderr) }
	if err := fs.Parse(args); err != nil {
		return exitUsage
	}
	if fs.NArg() != 1 {
		fmt.Fprintln(os.Stderr, "fsort sort: потрібна рівно одна тека (див. fsort help)")
		return exitUsage
	}
	src := fs.Arg(0)
	files, err := listFiles(src)
	if err != nil {
		fmt.Fprintln(os.Stderr, "fsort sort:", err)
		return exitUsage
	}
	root := *dest
	if root == "" {
		root = src
	}

	prefix := ""
	if *dryRun {
		prefix = "[dry-run] "
	}
	moved, failed := 0, 0
	for _, name := range files {
		catDir := filepath.Join(root, categoryOf(name))
		if !*dryRun {
			if err := os.MkdirAll(catDir, 0o755); err != nil {
				fmt.Fprintf(os.Stderr, "fsort sort: не вдалося створити %s: %v\n", catDir, err)
				failed++
				continue
			}
		}
		target := freeName(catDir, name)
		if !*dryRun {
			if err := os.Rename(filepath.Join(src, name), target); err != nil {
				fmt.Fprintf(os.Stderr, "fsort sort: не вдалося перемістити %s: %v\n", name, err)
				failed++
				continue
			}
		}
		fmt.Printf("%s%s -> %s\n", prefix, name, target)
		moved++
	}
	fmt.Printf("%sрозкладено: %d, помилок: %d\n", prefix, moved, failed)
	if failed > 0 {
		return exitError
	}
	return exitOK
}

func cmdStats(args []string) int {
	if len(args) != 1 {
		fmt.Fprintln(os.Stderr, "fsort stats: потрібна рівно одна тека (див. fsort help)")
		return exitUsage
	}
	files, err := listFiles(args[0])
	if err != nil {
		fmt.Fprintln(os.Stderr, "fsort stats:", err)
		return exitUsage
	}
	counts := map[string]int{}
	for _, f := range files {
		counts[categoryOf(f)]++
	}
	for _, c := range []string{"documents", "images", "video", "archives", other} {
		fmt.Printf("%-10s %d\n", c, counts[c])
	}
	fmt.Printf("%-10s %d\n", "total", len(files))
	return exitOK
}

func run(args []string) int {
	if len(args) == 0 {
		usage(os.Stderr)
		return exitUsage
	}
	switch args[0] {
	case "sort":
		return cmdSort(args[1:])
	case "stats":
		return cmdStats(args[1:])
	case "version", "--version":
		fmt.Println("fsort", version)
		return exitOK
	case "help", "-h", "--help":
		usage(os.Stdout)
		return exitOK
	default:
		fmt.Fprintf(os.Stderr, "fsort: невідома підкоманда %q\n\n", args[0])
		usage(os.Stderr)
		return exitUsage
	}
}

func main() {
	os.Exit(run(os.Args[1:]))
}
