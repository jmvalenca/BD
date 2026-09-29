import SwiftUI

@main
struct MovimentosApp: App {
    var body: some Scene {
        WindowGroup { ContentView() }
    }
}

// Gestão da ligação remota: arranca o servidor Docker por SSH e cria o túnel
// para aceder à aplicação Marimo em http://localhost:2718.
final class Manager: ObservableObject {
    @Published var status = "Desligado"
    @Published var destino: String { didSet { UserDefaults.standard.set(destino, forKey: "destino") } }
    @Published var repoDir: String { didSet { UserDefaults.standard.set(repoDir, forKey: "repoDir") } }
    private var tunnel: Process?
    private let porta = 2718

    init() {
        let d = UserDefaults.standard
        destino = d.string(forKey: "destino") ?? "josevalenca@mbp-de-jose"
        repoDir = d.string(forKey: "repoDir") ?? "~/Public/BD"
    }

    private func sshProcess(_ args: [String]) -> Process {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/usr/bin/ssh")
        p.arguments = ["-o", "ExitOnForwardFailure=yes", "-o", "ServerAliveInterval=30"] + args
        return p
    }

    func setStatus(_ s: String) { DispatchQueue.main.async { self.status = s } }

    // Arranca o servidor (docker compose) na máquina remota, via SSH.
    func arrancarServidor() {
        setStatus("A arrancar o servidor (docker compose)…")
        DispatchQueue.global().async {
            let p = self.sshProcess(["\(self.destino)",
                "cd '\(self.repoDir)' && docker compose up -d --build"])
            do { try p.run() } catch { self.setStatus("Erro ao ligar por SSH: \(error.localizedDescription)"); return }
            p.waitUntilExit()
            self.setStatus(p.terminationStatus == 0
                ? "Servidor ativo ✅ (docker compose no \(self.destino))"
                : "Falha ao arrancar ❌ — verifique a chave SSH e o Docker no servidor")
        }
    }

    // Cria o túnel SSH e abre o browser quando a aplicação responder.
    func ligar() {
        parar()
        setStatus("A ligar…")
        let p = sshProcess(["-N", "-L", "\(porta):127.0.0.1:\(porta)", destino])
        do { try p.run(); tunnel = p } catch { setStatus("Erro ao criar o túnel: \(error.localizedDescription)"); return }
        DispatchQueue.global().async {
            for _ in 0..<60 {
                Thread.sleep(forTimeInterval: 1)
                if self.tunnel == nil { return }  // foi desligado entretanto
                if self.responde() {
                    self.setStatus("Ligado ✅ http://localhost:\(self.porta)")
                    NSWorkspace.shared.open(URL(string: "http://localhost:\(self.porta)")!)
                    return
                }
            }
            self.setStatus("O servidor não respondeu em 60s ❌ (arrancou o servidor?)")
        }
    }

    func parar() {
        tunnel?.terminate()
        tunnel = nil
        setStatus("Desligado")
    }

    private func responde() -> Bool {
        let check = Process()
        check.executableURL = URL(fileURLWithPath: "/usr/bin/curl")
        check.arguments = ["-s", "-o", "/dev/null", "--max-time", "1", "http://127.0.0.1:\(porta)"]
        try? check.run()
        check.waitUntilExit()
        return check.terminationStatus == 0
    }
}

struct ContentView: View {
    @StateObject private var m = Manager()

    var body: some View {
        VStack(spacing: 14) {
            Text("Movimentos · Arminda Melo RL").font(.headline)
            TextField("Servidor (utilizador@host)", text: $m.destino)
                .textFieldStyle(.roundedBorder)
            TextField("Pasta do repo no servidor", text: $m.repoDir)
                .textFieldStyle(.roundedBorder)
            HStack(spacing: 12) {
                Button("Arrancar servidor") { m.arrancarServidor() }
                Button("Ligar") { m.ligar() }
                Button("Desligar") { m.parar() }
            }
            Text(m.status).foregroundStyle(.secondary)
        }
        .padding(24)
        .frame(minWidth: 480)
    }
}
