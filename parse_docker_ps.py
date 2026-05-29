import re
from pathlib import Path

INPUT_FILE = "docker_ps.txt"
OUTPUT_FILE = "docker_ps_ports.txt"
PORTS_FILTER_FILE = "ports_created.txt"


def load_allowed_ports(filter_path: str) -> set[str]:
    """
    从 ports_created.txt 加载允许的端口号，返回字符串集合，例如 {"8080", "8118", ...}
    """
    path = Path(filter_path)
    if not path.exists():
        # 如果没有过滤文件，则认为不过滤，返回空集合表示“不过滤”
        print(f"警告：未找到端口过滤文件 {filter_path}，将不过滤端口。")
        return set()

    ports: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        ports.add(line)
    return ports


def parse_docker_ps(input_path: str, output_path: str, ports_filter_path: str | None = None):
    in_file = Path(input_path)
    if not in_file.exists():
        raise FileNotFoundError(f"找不到输入文件：{input_path}")

    # 加载需要保留的端口集合；如果集合为空则表示不过滤
    allowed_ports: set[str] = set()
    if ports_filter_path:
        allowed_ports = load_allowed_ports(ports_filter_path)

    lines = in_file.read_text(encoding="utf-8").splitlines()

    # 跳过表头
    if not lines:
        print("文件为空")
        return

    header = lines[0]
    data_lines = lines[1:]

    results = []

    for line in data_lines:
        line = line.rstrip()
        if not line:
            continue

        # docker ps 输出是按列对齐的，列之间至少两个空格
        parts = re.split(r"\s{2,}", line.strip())
        # 预期格式：CONTAINER ID, IMAGE, COMMAND, CREATED, STATUS, PORTS, NAMES
        if len(parts) < 6:
            continue

        container_id = parts[0]
        ports_field = parts[5]  # PORTS 列

        # 只提取形如 0.0.0.0:5005->5005/tcp / [::]:5005->5005/tcp / 127.0.0.1:5005->... 等的“外部端口”
        host_ports = re.findall(r":(\d+)->", ports_field)

        # 去重：同一个容器的相同端口（例如 IPv4 + IPv6）只保留一条
        unique_ports = sorted(set(host_ports), key=int)

        for port in unique_ports:
            # 如果配置了过滤端口集合且不在集合中，则跳过
            if allowed_ports and port not in allowed_ports:
                continue
            results.append(f"{container_id}\t{port}")

    Path(output_path).write_text("\n".join(results) + ("\n" if results else ""), encoding="utf-8")
    print(f"已写入 {len(results)} 条记录到 {output_path}")


if __name__ == "__main__":
    parse_docker_ps(INPUT_FILE, OUTPUT_FILE, PORTS_FILTER_FILE)