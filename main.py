from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from celery import Celery
import requests
import uuid
import subprocess
from dotenv import load_dotenv
import os
import json
import shutil
import tempfile

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# Configure Celery
celery = Celery(
    'code_execution_app',
    broker=os.getenv('CELERY_BROKER_URL'),
    backend=os.getenv('CELERY_RESULT_BACKEND')
)

class TestCase(BaseModel):
    input: list
    expected_output: str

class CodeExecutionRequest(BaseModel):
    language: str
    code: str
    function_name: str
    imports: list
    test_cases: list[TestCase]
    callback_url: str

def validate_input(data: CodeExecutionRequest):
    if data.language not in ['python', 'js', 'java', 'rust', 'go', 'cpp']:
        raise ValueError("Invalid language")
    if not isinstance(data.code, str):
        raise ValueError("Invalid code")
    if not isinstance(data.imports, list):
        raise ValueError("Invalid imports")
    if not isinstance(data.test_cases, list):
        raise ValueError("Invalid test cases")
    for test_case in data.test_cases:
        if not isinstance(test_case.input, list) or not isinstance(test_case.expected_output, str):
            raise ValueError("Invalid test case data")

def run_code_in_docker(language, code, function_name, imports, test_cases):
    with tempfile.TemporaryDirectory() as temp_dir:
        if language == 'python':
            return run_python_code(code, function_name, imports, test_cases, temp_dir)
        elif language == 'js':
            return run_js_code(code, function_name, imports, test_cases, temp_dir)
        elif language == 'java':
            return run_java_code(code, function_name, imports, test_cases, temp_dir)
        elif language == 'rust':
            return run_rust_code(code, function_name, imports, test_cases, temp_dir)
        elif language == 'go':
            return run_go_code(code, function_name, imports, test_cases, temp_dir)
        elif language == 'cpp':
            return run_cpp_code(code, function_name, imports, test_cases, temp_dir)
        else:
            return "Invalid language specified."

def run_python_code(code, function_name, imports, test_cases, temp_dir):
    script = ""
    if imports:
        for imp in imports:
            script += f"import {imp}\n"
    script += f"{code}\n\n"
    script += "import json\n"
    script += "import time\n" 
    script += "test_cases = [\n"
    for test_case in test_cases:
        script += f"    ({json.dumps(test_case['input'])}, '{test_case['expected_output']}'),\n"
    script += "]\n"
    script += f"""
results = []
for inputs, expected in test_cases:
    try:
        start_time = time.perf_counter()
        result = {function_name}(*inputs)
        end_time = time.perf_counter()
        duration = end_time - start_time
        result_str = str(result)
        passed = result_str == expected
        results.append((inputs, expected, result_str, passed, duration))
    except Exception as e:
        results.append((inputs, expected, str(e), False, "0.0"))
for inputs, expected, result, passed, duration in results:
    print(json.dumps({{"inputs": inputs, "expected": expected, "result": result, "passed": passed, "time": duration}}))
"""
    script_path = os.path.join(temp_dir, "temp_script.py")
    with open(script_path, "w") as f:
        f.write(script)

    docker_run_command = (
        f"docker run --rm --user {os.getuid()}:{os.getgid()} -v {temp_dir}:/usr/src/app -w /usr/src/app --network none --memory=256m --cpus=1 "
        f"--ulimit cpu=10 --ulimit nofile=512 python:latest python temp_script.py"
    )
    process = subprocess.Popen(docker_run_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    if process.returncode == 0:
        return stdout.decode('utf-8')
    else:
        return stderr.decode('utf-8') or stdout.decode('utf-8')

def run_js_code(code, function_name, imports, test_cases, temp_dir):
    script = f"{code}\n\n"
    script += "const test_cases = [\n"
    for test_case in test_cases:
        script += f"    [{json.dumps(test_case['input'])}, '{test_case['expected_output']}'],\n"
    script += "];\n"
    script += f"""
const results = [];
for (const [inputs, expected] of test_cases) {{
    try {{
        const start = performance.now();
        const result = {function_name}(...inputs);
        const end = performance.now();
        const duration = (end - start).toString();
        const result_str = result.toString();
        const passed = result_str === expected;
        results.push({{inputs, expected, result: result_str, passed, time: duration}});
    }} catch (e) {{
        results.push({{inputs, expected, result: e.toString(), passed: false, time: "0.0"}});
    }}
}}
for (const {{inputs, expected, result, passed,time}} of results) {{
    console.log(JSON.stringify({{inputs, expected, result, passed,time}}));
}}
"""
    script_path = os.path.join(temp_dir, "temp_script.js")
    with open(script_path, "w") as f:
        f.write(script)

    docker_run_command = (
        f"docker run --rm --user {os.getuid()}:{os.getgid()} -v {temp_dir}:/usr/src/app -w /usr/src/app --network none --memory=256m --cpus=1 "
        f"--ulimit cpu=10 --ulimit nofile=512 node:latest node temp_script.js"
    )
    process = subprocess.Popen(docker_run_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    if process.returncode == 0:
        return stdout.decode('utf-8')
    else:
        return stderr.decode('utf-8') or stdout.decode('utf-8')

def run_java_code(code, function_name, imports, test_cases, temp_dir):
    imports_str = "\n".join(f"import {imp};" for imp in imports)
    
    test_cases_str = ""
    for test_case in test_cases:
        input_json = json.dumps(test_case['input'][0]).replace('"', '\\"')
        test_cases_str += f'        testCases.add(new Object[]{{gson.fromJson("{input_json}", List.class), "{test_case["expected_output"]}"}});\n'

    script = f"""
import java.util.*;
import com.google.gson.*;
import com.google.gson.reflect.TypeToken;
{imports_str}

public class Solution {{
    public static void main(String[] args) {{
        Gson gson = new GsonBuilder()
            .setLenient()
            .create();
        List<Object[]> testCases = new ArrayList<>();
{test_cases_str}
        
        for (Object[] testCase : testCases) {{
            try {{
                List<Object> inputs = (List<Object>) testCase[0];
                String expected = (String) testCase[1];
                
                Solution solution = new Solution();
                long startTime = System.nanoTime();
                
                Object result = solution.{function_name}(inputs);
                
                long endTime = System.nanoTime();
                long duration = (endTime - startTime);
                
                String resultStr = String.valueOf(result);
                
                Map<String, Object> output = new HashMap<>();
                // Match exactly what Python expects
                output.put("result", resultStr);
                output.put("expected", expected);
                output.put("inputs", inputs);  // Single list, not nested
                output.put("passed", resultStr.equals(expected));
                output.put("time", duration / 1_000_000_000.0);
                
                System.out.println(gson.toJson(output));  // No TEST_RESULT markers needed
            }} catch (Exception e) {{
                Map<String, Object> error = new HashMap<>();
                error.put("result", e.toString());
                error.put("expected", testCase[1]);
                error.put("inputs", testCase[0]);
                error.put("passed", false);
                error.put("time", 0.0);
                
                System.out.println(gson.toJson(error));
            }}
        }}
    }}
    
    {code}
}}"""
    # Write the Java file
    script_path = os.path.join(temp_dir, "Solution.java")
    with open(script_path, "w") as f:
        f.write(script)

    print("Generated Java code:")
    print(script)

    # Compile and run commands
    docker_compile_command = (
        f"docker run --rm -v {temp_dir}:/app -w /app openjdk:11 bash -c '"
        f"curl -s https://repo1.maven.org/maven2/com/google/code/gson/gson/2.8.9/gson-2.8.9.jar -o gson.jar && "
        f"javac -cp gson.jar Solution.java'"
    )

    docker_run_command = (
        f"docker run --rm -v {temp_dir}:/app -w /app openjdk:11 "
        f"java -cp '.:/app/gson.jar' Solution"
    )

    try:
        # Compile
        compile_result = subprocess.run(
            docker_compile_command, 
            shell=True, 
            capture_output=True, 
            text=True,
            cwd=temp_dir
        )
        
        if compile_result.returncode != 0:
            print("Compilation Error:", compile_result.stderr)
            return json.dumps({
                "results": [],
                "all_passed": False,
                "error": "Compilation error",
                "error_details": compile_result.stderr or compile_result.stdout
            })

        # Run
        run_result = subprocess.run(
            docker_run_command, 
            shell=True, 
            capture_output=True, 
            text=True,
            cwd=temp_dir
        )
        
        output = run_result.stdout or run_result.stderr
        print("Raw Java Output:", output)  # Debug line
        
        try:
            result = json.loads(output)
            print("Parsed JSON:", result)  # Debug line
        except json.JSONDecodeError as e:
            print("JSON Parse Error:", str(e))
            print("Failed to parse:", output)
            
        return json.dumps({
            "results": [{
                "input": test_case['input'],
                "expected_output": test_case['expected_output'],
                "actual_output": result.get('result', 'Error: No result'),
                "passed": result.get('passed', False),
                "time": str(result.get('time', 0.0)),
                "memory": "N/A"
            } for test_case, result in zip(test_cases, [result])],
            "all_passed": all(r.get("passed", False) for r in [result])
        })

    except Exception as e:
        print("Exception:", str(e))  # Debug line
        return json.dumps({
            "results": [],
            "all_passed": False,
            "error": "Runtime error",
            "error_details": str(e)
        })
def run_rust_code(code, function_name, imports, test_cases, temp_dir):
    cargo_toml = """
    [package]
    name = "code_execution"
    version = "0.1.0"
    edition = "2018"

    [dependencies]
    serde = "1.0"
    serde_json = "1.0"
    """

    imports_section = "\n".join([f"use {imp};" for imp in imports])
    
    main_rs = f"""
    extern crate serde;
    extern crate serde_json;
    use serde_json::json;
    use std::time::Instant;

    {imports_section}

    {code}

    fn main() {{
        let test_cases = vec![
    """
    for test_case in test_cases:
        inputs_str = ", ".join(f"vec!{v}" for v in test_case['input'])
        main_rs += f"            (({inputs_str}), \"{test_case['expected_output']}\"),\n"
    main_rs += f"""
        ];

        for (inputs, expected) in test_cases {{
            let start = Instant::now(); 
            let result = {function_name}(inputs.0.clone(), inputs.1.clone());
            let duration = start.elapsed();
            let result_str = format!("{{:.1}}", result);
            let passed = result_str == expected;
            let inputs_json = serde_json::to_string(&inputs).unwrap();
            println!("{{{{\\"inputs\\": {{}}, \\"expected\\": \\"{{}}\\", \\"result\\": \\"{{}}\\", \\"passed\\": {{}}, \\"time\\": \\"{{:?}}\\", \\"memory\\": \\"N/A\\"}}}}",
                     inputs_json, expected, result_str, passed, duration);
        }}
    }}
    """

    os.makedirs(os.path.join(temp_dir, 'src'), exist_ok=True)

    with open(os.path.join(temp_dir, 'Cargo.toml'), 'w') as f:
        f.write(cargo_toml)

    with open(os.path.join(temp_dir, 'src/main.rs'), 'w') as f:
        f.write(main_rs)

    docker_build_command = (
        f"docker run --rm --user {os.getuid()}:{os.getgid()} -v {temp_dir}:/usr/src/code_execution -w /usr/src/code_execution rust:latest cargo build --release"
    )
    process = subprocess.Popen(docker_build_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    if process.returncode != 0:
        return stderr.decode('utf-8') or stdout.decode('utf-8')
    container_name = f"code_exec_{uuid.uuid4()}"
    docker_run_command = (
        f"docker run --name {container_name} --rm --user {os.getuid()}:{os.getgid()} -v {temp_dir}:/usr/src/code_execution -w /usr/src/code_execution --network none --memory=256m --cpus=1 "
        f"--ulimit cpu=10 --ulimit nofile=512 rust:latest ./target/release/code_execution"
    )
    process = subprocess.Popen(docker_run_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    if process.returncode == 0:
        output = stdout.decode('utf-8')
    else:
        output = stderr.decode('utf-8') or stdout.decode('utf-8')
        
    return output
    
    
def run_go_code(code, function_name, imports, test_cases, temp_dir):
    script = f"package main\n\n"
    script += "import (\n"
    script += "    \"encoding/json\"\n"
    script += "    \"fmt\"\n"
    script += "    \"sort\"\n"
    script += "    \"time\"\n"
    if imports:
        for imp in imports:
            script += f"    \"{imp}\"\n"
    script += ")\n\n"
    script += f"{code}\n\n"
    script += "func main() {\n"
    script += "    testCases := []struct {\n"
    script += "        inputs [][]int\n"
    script += "        expected string\n"
    script += "    }{\n"
    for test_case in test_cases:
        input_str = ', '.join([str(i).replace('[', '{').replace(']', '}') for i in test_case['input']])
        script += f"        {{inputs: [][]int{{{input_str}}}, expected: \"{test_case['expected_output']}\"}},\n"
    script += "    }\n\n"
    script += f"""
    
    for _, testCase := range testCases {{
        start := time.Now()
        result := {function_name}(testCase.inputs[0], testCase.inputs[1])
        resultStr := fmt.Sprintf("%.1f", result)
        passed := resultStr == testCase.expected
        elapsed := time.Since(start)
        resultJSON, _ := json.Marshal(map[string]interface{{}}{{
            "inputs": testCase.inputs,
            "expected": testCase.expected,
            "result": resultStr,
            "passed": passed,
            "time": elapsed,
        }})
        fmt.Println(string(resultJSON))
    }}
}}
"""
    script_path = os.path.join(temp_dir, "main.go")
    with open(script_path, "w") as f:
        f.write(script)

    docker_run_command = (
        f"docker run --rm --user {os.getuid()}:{os.getgid()} -v {temp_dir}:/usr/src/app -w /usr/src/app --network none --memory=256m --cpus=1 "
        f"--ulimit cpu=10 --ulimit nofile=512 golang:latest go run main.go"
    )
    process = subprocess.Popen(docker_run_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    if process.returncode == 0:
        return stdout.decode('utf-8')
    else:
        return stderr.decode('utf-8') or stdout.decode('utf-8')

def run_cpp_code(code, function_name, imports, test_cases, temp_dir):
    imports_str = "\n".join(f"#include <{imp}>" for imp in imports)
    
    test_cases_str = ""
    for test_case in test_cases:
        input1_str = ', '.join(map(str, test_case['input'][0]))
        input2_str = ', '.join(map(str, test_case['input'][1]))
        test_cases_str += f'test_cases.push_back(TestCase{{{{{input1_str}}}, {{{input2_str}}}, "{test_case["expected_output"]}"}});\n'
    
    script = f"""
    #include <iostream>
    #include <vector>
    #include <string>
    #include <algorithm>
    #include <iomanip>
    #include <sstream>
    #include <chrono>

    {imports_str}
    using namespace std;
    
    struct TestCase {{
        vector<int> input1;
        vector<int> input2;
        string expected_output;
    }};
    
    {code}

    string vec_to_string(const vector<int>& vec) {{
        ostringstream oss;
        for (size_t i = 0; i < vec.size(); ++i) {{
            if (i != 0) oss << ",";
            oss << vec[i];
        }}
        return oss.str();
    }}

    string to_json(const TestCase& test_case, const string& result, bool passed, double duration) {{
        ostringstream oss;
        oss << fixed << setprecision(1);
        oss << "{{\\"inputs\\": \\"[[" << vec_to_string(test_case.input1) << "], [" << vec_to_string(test_case.input2) << "]]\\", ";
        oss << "\\"expected\\": \\"" << test_case.expected_output << "\\", ";
        oss << "\\"result\\": \\"" << result << "\\", ";
        oss << "\\"passed\\": " << (passed ? "true" : "false") << ", ";
        oss << "\\"time\\": \\"" << duration << "\\"}}";
        return oss.str();
    }}

    int main() {{
        vector<TestCase> test_cases;
        {test_cases_str}

        for (const auto& test_case : test_cases) {{
            try {{
                auto start = std::chrono::high_resolution_clock::now();
                float result = {function_name}(test_case.input1, test_case.input2);
                auto end = std::chrono::high_resolution_clock::now(); 
                std::chrono::duration<double> duration = end - start; 
                ostringstream result_str;
                result_str << fixed << setprecision(1) << result;
                bool passed = result_str.str() == test_case.expected_output;
                cout << to_json(test_case, result_str.str(), passed, duration.count()) << endl;
            }} catch (const exception& e) {{
                cout << to_json(test_case, e.what(), false, 0.0) << endl;
            }}
        }}
        return 0;
    }}
    """

    script_path = os.path.join(temp_dir, "main.cpp")
    with open(script_path, "w") as f:
        f.write(script)

    docker_run_command = (
        f"docker run --rm --user {os.getuid()}:{os.getgid()} -v {temp_dir}:/usr/src/app -w /usr/src/app --network none --memory=256m --cpus=1 "
        f"--ulimit cpu=10 --ulimit nofile=512 gcc:latest bash -c 'g++ -o main main.cpp && chmod +x main && ./main'"
    )
    process = subprocess.Popen(docker_run_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    if process.returncode == 0:
        return stdout.decode('utf-8')
    else:
        return stderr.decode('utf-8') or stdout.decode('utf-8')

def try_parse_list(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value

def get_docker_memory_usage(container_name):
    docker_stats_command = f"docker stats {container_name} --no-stream --format '{{{{.MemUsage}}}}'"
    stats_process = subprocess.Popen(docker_stats_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stats_stdout, stats_stderr = stats_process.communicate()

    if stats_process.returncode == 0:
        memory_usage = stats_stdout.decode('utf-8').strip().split('/')[0].strip()
    else:
        memory_usage = "N/A"

    return memory_usage

@celery.task(name='code_execution_app.execute_code_task')
def execute_code_task(data, id):
    execution_id = id
    language = data['language']
    code = data['code']
    function_name = data['function_name']
    imports = data['imports']
    test_cases = data['test_cases']
    callback_url = data['callback_url']
    results = []

    actual_output = run_code_in_docker(language, code, function_name, imports, test_cases)
    if not actual_output:
        actual_output = "No output from Docker execution."

    # Parse the single JSON output from Java
    try:
        # Clean up any leading/trailing whitespace
        actual_output = actual_output.strip()
        print(f"Processing output: {actual_output}")  # Debug log
        
        result_json = json.loads(actual_output)
        print(f"Parsed JSON: {result_json}")  # Debug log
        
        # Create a single result object in our expected format
        result = {
            'input': result_json.get('inputs', []),  # Use get() with default
            'expected_output': result_json.get('expected', ''),
            'actual_output': result_json.get('result', ''),
            'passed': result_json.get('passed', False),
            'time': str(result_json.get('time', 0.0)),
            'memory': 'N/A'
        }
        
        results.append(result)
        
        response_payload = {
            'id': execution_id,
            'results': results,
            'all_passed': result.get('passed', False)
        }

    except Exception as e:
        print(f"Error processing results: {str(e)}")  # Debug log
        response_payload = {
            'id': execution_id,
            'results': [],
            'all_passed': False,
            'error': f"Error processing results: {str(e)}",
            'error_details': actual_output
        }

    try:
        print(f"Sending callback payload: {json.dumps(response_payload, indent=2)}")
        response = requests.post(callback_url, json=response_payload)
        print(f"Callback response status: {response.status_code}")
        print(f"Callback response content: {response.text}")
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error sending callback: {e}")

    return response_payload
@app.post("/execute")
async def execute_code(request: CodeExecutionRequest):
    try:
        id = str(uuid.uuid4())
        validate_input(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    execute_code_task.delay(request.dict(), id)
    return {"message": "Code execution started", "id": id}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)