import SwiftUI

@main
struct MovimentosApp: App {
    var body: some Scene {
        WindowGroup { ContentView() }
    }
}

// Onde corre o servidor (Docker/Colima com PostgreSQL + marimo).
enum Modo: String {
    case local    // neste Mac
    case remoto   // noutro Mac, por SSH (com túnel para o porto 2718)
}

// Arranca o servidor (Colima + docker compose, através do arrancar.sh do repo)
// e dá acesso à aplicação Marimo em http://localhost:2718:
//  - modo local:  diretamente;
//  - modo remoto: através de um túnel SSH.
final class Manager: ObservableObject {
    @Published var status = "Desligado"
    @Published var ocupado = false
    // Escolhido no arranque da app (nil = ainda não escolhido).
    @Published var modo: Modo? = nil
    // Último modo usado: fica como opção por omissão no arranque seguinte.
    @Published var ultimoModo: Modo
    @Published var destino: String { didSet { UserDefaults.standard.set(destino, forKey: "destino") } }
    @Published var repoDir: String { didSet { UserDefaults.standard.set(repoDir, forKey: "repoDir") } }
    @Published var repoLocal: String { didSet { UserDefaults.standard.set(repoLocal, forKey: "repoLocal") } }
    private var tunnel: Process?
    private var geracao = 0   // muda a cada "Desligar": cancela esperas em curso
    private let porta = 2718
    private let opcoesSSH = ["-o", "BatchMode=yes", "-o", "ExitOnForwardFailure=yes",
                             "-o", "ServerAliveInterval=30"]

    init() {
        let d = UserDefaults.standard
        destino = d.string(forKey: "destino") ?? "josevalenca@mbp-de-jose"
        repoDir = d.string(forKey: "repoDir") ?? "~/Public/BD"
        repoLocal = d.string(forKey: "repoLocal") ?? "~/Public/BD"
        ultimoModo = Modo(rawValue: d.string(forKey: "modo") ?? "") ?? .local
    }

    func setStatus(_ s: String) { DispatchQueue.main.async { self.status = s } }
    private func setOcupado(_ b: Bool) { DispatchQueue.main.async { self.ocupado = b } }

    func escolher(_ m: Modo) {
        modo = m
        ultimoModo = m
        UserDefaults.standard.set(m.rawValue, forKey: "modo")
        status = m == .local ? "Servidor local (Colima neste Mac)" : "Desligado"
    }

    // Volta ao ecrã de escolha local/remoto.
    func mudarModo() {
        parar()
        modo = nil
    }

    // Corre um comando e devolve o código de saída e a última linha escrita
    // (para mostrar o erro no estado da app).
    private func correr(_ executavel: String, _ args: [String]) -> (Int32, String) {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: executavel)
        p.arguments = args
        var env = ProcessInfo.processInfo.environment
        env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + (env["PATH"] ?? "/usr/bin:/bin:/usr/sbin:/sbin")
        p.environment = env
        let pipe = Pipe()
        p.standardOutput = pipe
        p.standardError = pipe
        do { try p.run() } catch { return (-1, error.localizedDescription) }
        let dados = pipe.fileHandleForReading.readDataToEndOfFile()
        p.waitUntilExit()
        let saida = String(decoding: dados, as: UTF8.self)
        let ultima = saida.split(whereSeparator: \.isNewline).last.map(String.init) ?? ""
        return (p.terminationStatus, ultima)
    }

    // Caminho para usar num comando de shell remoto (com ~ expandido no servidor).
    private func caminhoShell(_ p: String) -> String {
        func aspas(_ s: String) -> String { "'" + s.replacingOccurrences(of: "'", with: "'\\''") + "'" }
        if p == "~" { return "\"$HOME\"" }
        if p.hasPrefix("~/") { return "\"$HOME\"/" + aspas(String(p.dropFirst(2))) }
        return aspas(p)
    }

    // Arranca o Colima (se preciso) e os containers, neste Mac ou no servidor por SSH.
    func arrancarServidor() {
        guard let modo = modo else { return }
        ocupado = true
        status = modo == .local
            ? "A arrancar o Colima e os containers… (a 1.ª vez demora)"
            : "A arrancar o servidor remoto (Colima + docker compose)…"
        let repoLocal = (self.repoLocal as NSString).expandingTildeInPath
        let repoRemoto = repoDir.hasSuffix("/") ? String(repoDir.dropLast()) : repoDir
        let destino = self.destino
        DispatchQueue.global().async {
            let r: (Int32, String) = modo == .local
                ? self.correr("/bin/bash", [repoLocal + "/arrancar.sh"])
                : self.correr("/usr/bin/ssh", self.opcoesSSH +
                    [destino, "/bin/bash " + self.caminhoShell(repoRemoto + "/arrancar.sh")])
            if r.0 == 0 {
                self.setStatus(modo == .local
                    ? "Servidor ativo ✅ — clique em «Abrir no browser»"
                    : "Servidor ativo ✅ (\(destino)) — clique em «Ligar»")
            } else if modo == .remoto && r.0 == 255 {
                self.setStatus("Falha na ligação SSH ❌ — \(r.1)")
            } else {
                self.setStatus("Falha ao arrancar ❌ — \(r.1.isEmpty ? "verifique o Colima" : r.1)")
            }
            self.setOcupado(false)
        }
    }

    // Modo remoto: cria o túnel SSH. Em ambos os modos, espera que a
    // aplicação responda e abre o browser.
    func ligar() {
        guard let modo = modo else { return }
        parar()
        let g = geracao
        if modo == .remoto {
            if responde() {
                setStatus("O porto \(porta) já está ocupado ❌ — há um servidor local a correr?")
                return
            }
            setStatus("A ligar…")
            let p = Process()
            p.executableURL = URL(fileURLWithPath: "/usr/bin/ssh")
            p.arguments = opcoesSSH + ["-N", "-L", "\(porta):127.0.0.1:\(porta)", destino]
            do { try p.run(); tunnel = p } catch { setStatus("Erro ao criar o túnel: \(error.localizedDescription)"); return }
        } else {
            setStatus("A aguardar a aplicação…")
        }
        DispatchQueue.global().async {
            for _ in 0..<60 {
                Thread.sleep(forTimeInterval: 1)
                if self.geracao != g { return }   // foi desligado entretanto
                if modo == .remoto, let t = self.tunnel, !t.isRunning {
                    self.setStatus("O túnel SSH falhou ❌ (sem acesso SSH ou porto \(self.porta) ocupado)")
                    return
                }
                if self.responde() {
                    self.setStatus("Ligado ✅ http://localhost:\(self.porta)")
                    DispatchQueue.main.async {
                        NSWorkspace.shared.open(URL(string: "http://localhost:\(self.porta)")!)
                    }
                    return
                }
            }
            self.setStatus("A aplicação não respondeu em 60s ❌ (arrancou o servidor?)")
        }
    }

    func parar() {
        geracao += 1
        tunnel?.terminate()
        tunnel = nil
        setStatus(modo == .local ? "Servidor local (Colima neste Mac)" : "Desligado")
    }

    private func responde() -> Bool {
        let check = Process()
        check.executableURL = URL(fileURLWithPath: "/usr/bin/curl")
        check.arguments = ["-s", "-o", "/dev/null", "--max-time", "1", "http://127.0.0.1:\(porta)"]
        do { try check.run() } catch { return false }
        check.waitUntilExit()
        return check.terminationStatus == 0
    }
}

struct ContentView: View {
    @StateObject private var m = Manager()

    var body: some View {
        Group {
            if let modo = m.modo {
                PainelView(m: m, modo: modo)
            } else {
                EscolhaView(m: m)
            }
        }
        .padding(24)
        .frame(minWidth: 480)
        // ao sair da app, fechar o túnel SSH (se existir)
        .onReceive(NotificationCenter.default.publisher(for: NSApplication.willTerminateNotification)) { _ in
            m.parar()
        }
    }
}

// Ecrã inicial: escolher entre servidor local e servidor remoto.
struct EscolhaView: View {
    @ObservedObject var m: Manager

    var body: some View {
        VStack(spacing: 16) {
            Text("Movimentos · Arminda Melo RL").font(.headline)
            Text("Onde está o servidor?").foregroundStyle(.secondary)
            HStack(spacing: 16) {
                opcao(.local, "Servidor local", "desktopcomputer", "Colima neste Mac")
                opcao(.remoto, "Servidor remoto", "network", "Outro Mac, por SSH")
            }
        }
    }

    private func opcao(_ modo: Modo, _ titulo: String, _ icone: String, _ detalhe: String) -> some View {
        Button { m.escolher(modo) } label: {
            VStack(spacing: 6) {
                Image(systemName: icone).font(.system(size: 28))
                Text(titulo).bold()
                Text(detalhe).font(.caption).foregroundStyle(.secondary)
            }
            .frame(width: 170, height: 100)
        }
        .buttonStyle(CartaoStyle(destacado: m.ultimoModo == modo))
        // Enter escolhe o modo usado da última vez (destacado)
        .keyboardShortcut(m.ultimoModo == modo ? KeyboardShortcut.defaultAction : nil)
    }
}

// Botão grande em forma de cartão (os botões normais do macOS têm altura fixa).
struct CartaoStyle: ButtonStyle {
    var destacado: Bool

    func makeBody(configuration: Configuration) -> some View {
        let forma = RoundedRectangle(cornerRadius: 10)
        return configuration.label
            .padding(8)
            .background(forma.fill(Color.secondary.opacity(configuration.isPressed ? 0.25 : 0.1)))
            .overlay(forma.stroke(destacado ? Color.accentColor : Color.secondary.opacity(0.3),
                                  lineWidth: destacado ? 2 : 1))
            .contentShape(forma)
    }
}

struct PainelView: View {
    @ObservedObject var m: Manager
    let modo: Modo

    var body: some View {
        VStack(spacing: 14) {
            Text("Movimentos · Arminda Melo RL").font(.headline)
            HStack {
                Label(modo == .local ? "Servidor local" : "Servidor remoto",
                      systemImage: modo == .local ? "desktopcomputer" : "network")
                Spacer()
                Button("Mudar…") { m.mudarModo() }.disabled(m.ocupado)
            }
            if modo == .remoto {
                TextField("Servidor (utilizador@host)", text: $m.destino)
                    .textFieldStyle(.roundedBorder)
                TextField("Pasta do repo no servidor", text: $m.repoDir)
                    .textFieldStyle(.roundedBorder)
            } else {
                TextField("Pasta do repo neste Mac", text: $m.repoLocal)
                    .textFieldStyle(.roundedBorder)
            }
            HStack(spacing: 12) {
                Button("Arrancar servidor") { m.arrancarServidor() }
                if modo == .remoto {
                    Button("Ligar") { m.ligar() }
                    Button("Desligar") { m.parar() }
                } else {
                    Button("Abrir no browser") { m.ligar() }
                }
            }
            .disabled(m.ocupado)
            Text(m.status).foregroundStyle(.secondary).multilineTextAlignment(.center)
        }
    }
}
