// Optional P5-0 research tool. Never executes a generated game executable.
// Run from the repository root; all inputs/outputs must be private working copies.
using System.Security.Cryptography;
using System.Text.Json;
using Octodiff.Core;
using Octodiff.Diagnostics;

const string BasisHash = "83915175abaf8a65dab96fc42f1feed24a78f55dc8b28a736b61ffa83314b545";
const string DeltaHash = "ebaafd49de3dddec39b695c4fb66b29a2fb860285b6e3b09e36496e81dca8272";
if (args.Length != 3)
    throw new ArgumentException("Expected private basis, delta, new output paths; run from repository root.");
var root = Path.GetFullPath(".local/p5-jp") + Path.DirectorySeparatorChar;
var paths = args.Select(Path.GetFullPath).ToArray();
foreach (var path in paths)
{
    if (!path.StartsWith(root, StringComparison.OrdinalIgnoreCase))
        throw new ArgumentException("Paths must stay under .local/p5-jp.");
    // Resolve/reject directory links before opening a nominally private path.
    for (var parent = new DirectoryInfo(Path.GetDirectoryName(path)!); parent != null; parent = parent.Parent)
        if ((parent.Attributes & FileAttributes.ReparsePoint) != 0)
            throw new ArgumentException("Linked directories are not accepted.");
    if (File.Exists(path) && (File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0)
        throw new ArgumentException("Linked files are not accepted.");
}
string HashFile(string path) => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();
if (HashFile(paths[0]) != BasisHash || HashFile(paths[1]) != DeltaHash)
    throw new InvalidDataException("STOP: pinned English basis or upstream delta hash mismatch.");
var pending = paths[2] + ".pending";
var rejected = paths[2] + ".rejected";
if (new[] { paths[2], pending, rejected }.Any(File.Exists))
    throw new IOException("Refusing to overwrite any previous attempt.");
var result = new Dictionary<string, object?> {
    ["basis_sha256"] = BasisHash, ["delta_sha256"] = DeltaHash,
    ["octodiff_assembly_version"] = typeof(DeltaApplier).Assembly.GetName().Version?.ToString(),
    ["runtime_version"] = Environment.Version.ToString(), ["skip_hash_check"] = false,
    ["validation"] = "Octodiff target hash check; not a whole-basis hash assertion"
};
try
{
    using (var basis = File.OpenRead(paths[0]))
    using (var delta = File.OpenRead(paths[1]))
    using (var output = new FileStream(pending, FileMode.CreateNew, FileAccess.ReadWrite))
    {
        var reader = new BinaryDeltaReader(delta, new NullProgressReporter());
        result["expected_output_hash"] = Convert.ToHexString(reader.ExpectedHash).ToLowerInvariant();
        new DeltaApplier { SkipHashCheck = false }.Apply(basis, reader, output);
    }
    File.Move(pending, paths[2]);
    result["status"] = "ACCEPTED";
    result["output_sha256"] = HashFile(paths[2]);
    result["output_size"] = new FileInfo(paths[2]).Length;
    Console.WriteLine(JsonSerializer.Serialize(result, new JsonSerializerOptions { WriteIndented = true }));
    return 0;
}
catch (Exception error)
{
    if (File.Exists(pending)) File.Move(pending, rejected);
    result["status"] = "REJECTED";
    result["exception_type"] = error.GetType().FullName;
    result["error"] = error.Message;
    if (File.Exists(rejected)) {
        result["rejected_output_sha256"] = HashFile(rejected);
        result["rejected_output_size"] = new FileInfo(rejected).Length;
    }
    Console.WriteLine(JsonSerializer.Serialize(result, new JsonSerializerOptions { WriteIndented = true }));
    return 2;
}
