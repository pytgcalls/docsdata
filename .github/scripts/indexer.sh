json="{";
first=true;
exclude_files=(
"config.xml"
"map.json"
"indexer.sh"
"README.md"
"base.xml"
".gitignore"
".vscode"
".github"
)

is_excluded() {
  local file=$1
  for exclude in "${exclude_files[@]}"; do
    if [[ $(basename "$file") == "$exclude" ]]; then
      return 0
    fi
  done
  return 1
}

iter_files() {
  local dir="$1"
  local files=()
  local sub_files=()
  for file in "$dir"/*; do
    if [ -d "$file" ]; then
      mapfile -t sub_files < <(iter_files "$file")
      files+=("${sub_files[@]}")
    else
      files+=("$file")
    fi
  done
  printf "%s\n" "${files[@]}"
}

while IFS= read -r file; do
  if ! is_excluded "$file"; then
    if [ "$first" = false ]; then
      json+=",";
    fi
    json+="\"${file:1}\": $(printf '%s' "$(<"$file")" | jq -Rsa .)";
    first=false;
  fi
done < <(iter_files .)
echo "$json}" > "map.json";