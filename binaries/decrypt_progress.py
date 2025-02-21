async def run_mp4decrypt(executable, track):
    # Define your subprocess command
    cmd = [
        executable,
        "--show-progress",
        "--key", f"{track.kid.lower()}:{track.key.lower()}",
        track.locate(),
        dec,
    ]

    # Start the subprocess asynchronously
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    number2 = 1

    # Read stdout asynchronously and update progress bar
    with tqdm(total=number2) as pbar:
        while True:
            # Read line from stdout asynchronously
            line = await process.stdout.readline()
            if not line:
                break
            line = line.decode().strip()

            # Search for progress numbers
            match = re.search(r'(\d+)/(\d+)', line)
            if match:
                number1 = int(match.group(1)) if match.group(1) else 0
                number2 = int(match.group(2)) if match.group(2) else 1
                pbar.update(number1 - pbar.n)  # Update progress bar
            else:
                print(line)

    # Wait for the subprocess to complete
    await process.wait()

async def call():
    await run_mp4decrypt(executable, track)

asyncio.run(call())

async def run_shaka(executable, track):
    cmd = [
        executable,
        f'input={track.locate()},stream={track.__class__.__name__.lower().replace("track", "")},output={dec}',
        "--enable_raw_key_decryption", "--keys",
        ",".join([
            f"label=0:key_id={track.kid.lower()}:key={track.key.lower()}",
            f"label=1:key_id=00000000000000000000000000000000:key={track.key.lower()}",
        ]),
        "--temp_dir", directories.temp
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Initialize variables for progress tracking
    number1 = 0
    number2 = 1

    # Read stdout asynchronously and update progress bar
    with tqdm(total=number2) as pbar:
        while True:
            # Read line from stdout asynchronously
            line = await process.stdout.readline()
            if not line:
                break
            line = line.decode().strip()

            # Search for progress numbers
            match = re.search(r'(\d+)/(\d+)', line)
            if match:
                number1 = int(match.group(1)) if match.group(1) else 0
                number2 = int(match.group(2)) if match.group(2) else 1
                pbar.n = number2
                pbar.update(number1 - pbar.n)  # Update progress bar
            else:
                print("\n" + line)  # Print non-progress lines if needed

    # Wait for the subprocess to complete
    await process.wait()
    
async def call(executable, track):
    await run_shaka(executable, track)
asyncio.run(call(executable, track))
